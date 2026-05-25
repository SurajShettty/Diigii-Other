"""
doc_to_ai_search_gemini.py
--------------------------
Same as doc_to_ai_search.py but uses Google Gemini (free tier) instead of
Claude. Produces identical JSON + cleaned Markdown for RAG ingestion.

Pipeline:
    .md (raw)  ->  Gemini 2.5 Flash (JSON mode)  ->  structured JSON
                                                ->  rendered Markdown

Setup (one-time):
    pip install google-genai
    1. Go to https://aistudio.google.com/apikey
    2. Click "Create API key" (free, no billing required)
    3. In PowerShell:
           $env:GEMINI_API_KEY = "AIza...your-key..."
       Or permanent:
           [Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AIza...", "User")

Free-tier limits (Gemini 2.5 Flash, as of 2025-2026):
    10 requests/min, 1500 requests/day, 250K tokens/min.
    Script paces calls at ~6s apart to stay under the 10 RPM cap.

Usage:
    Easiest:  edit DEFAULT_INPUT / DEFAULT_OUTPUT below, then just run the file.

    CLI also still works (overrides the defaults):
        python doc_to_ai_search_gemini.py "path/to/doc.md" -o ai_docs_out
        python doc_to_ai_search_gemini.py "docs/" -o ai_docs_out -m "Staff Management"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError

# ===== EDIT THESE FOR YOUR RUN =====
DEFAULT_INPUT  = r"C:\Users\suraj\Downloads\My Python\Digii Other\Documentations"
DEFAULT_OUTPUT = r"C:\Users\suraj\Downloads\My Python\Digii Other\ai_docs_out\Mess Management"
DEFAULT_MODULE = None   # e.g. "Staff Management", or leave as None
# ====================================

MODEL = "gemini-2.5-flash"
MAX_OUTPUT_TOKENS = 32768   # 2.5 Flash supports up to 65,536; 32K handles big feature tables
MAX_RETRIES = 3
MIN_SECONDS_BETWEEN_CALLS = 6.5  # stay under 10 RPM on free tier

SYSTEM_PROMPT = """You are a documentation transformer for a RAG (retrieval-augmented generation) chatbot that answers user questions about the Digii campus-management platform (LMS / admin / HR / academics).

Your job: take a raw Markdown document describing features and emit ONE JSON object with rich, search-optimised content.

OUTPUT SCHEMA (return JSON only):
{
  "doc": {
    "title": "string",
    "module": "string (e.g. 'Staff Management', 'Admissions', 'EMS', 'CHC')",
    "summary": "1-3 sentence overview of the document",
    "prerequisites": [
      {"name": "string", "description": "string"}
    ],
    "tags": ["string", ...]
  },
  "chunks": [
    {
      "id": "kebab-case-unique-id",
      "feature_name": "human-readable feature name",
      "category": "sub-area within module",
      "what_it_does": "Plain-language 1-3 sentence description.",
      "why_it_matters": "Business value, 1-3 sentences.",
      "how_to_use": ["Step 1...", "Step 2...", ...],
      "examples": ["Concrete example narrative 1", "..."],
      "keywords": ["15-25 search terms incl. synonyms, action verbs, abbreviations, singular+plural forms"],
      "synonyms": ["alternate terms users may type"],
      "user_questions": [
        "5-12 realistic user questions this chunk answers, phrased naturally",
        "How do I ...?", "Can I ...?", "What happens when ...?"
      ],
      "related_features": ["ids of other chunks in this doc that connect"],
      "tags": ["topical tags"]
    }
  ]
}

RULES:
1. Clean encoding artefacts. Common mojibake patterns to fix:
   - 'â' or 'â' garbage -> em dash '—'
   - 'â' -> '’' apostrophe
   - 'â' / 'â' -> curly quotes
   - stray 'Â' bytes -> remove
   Normalise to clean unicode.
2. Expand acronyms the first time they appear in a chunk (HR -> Human Resources (HR), EMS -> Examination Management System (EMS), CHC -> Campus Help Centre (CHC), LMS, KPI, OBE, DAG, REC).
3. Keywords must aggressively cover the search space:
   - feature name + variants (e.g. 'staff', 'employee', 'faculty', 'teacher', 'employees')
   - action verbs (add, create, register, onboard, edit, update, modify, deactivate, disable, suspend, download, export)
   - user roles (HR admin, registrar, super admin, principal)
   - common misspellings and informal phrasings ('staff acc', 'emp record')
   - related noun forms (bulk upload, excel template, csv, account creation)
4. user_questions must read like real chatbot queries — short, conversational, sometimes incomplete.
   Good: "How do I add 50 staff at once?", "Why can't a deactivated staff log in?"
   Bad:  "What is the functionality for performing bulk creation of staff records?"
5. Each chunk is SELF-CONTAINED. A retrieval system pulling a single chunk should let the model answer related questions without seeing siblings.
6. Preserve any numbered step lists exactly — these are how-to procedures users need verbatim.
7. If the source has tables, treat each row as a candidate chunk; merge only if rows clearly describe the same feature.
8. Do not invent functionality. If a field is empty in the source, leave the corresponding output field as an empty array/string rather than fabricating content.
9. Return ONLY the JSON object — no commentary, no markdown fences."""


# ----------------------------- text cleanup -----------------------------

_MOJIBAKE = {
    "â": "—",
    "â": "–",
    "â": "’",
    "â": "‘",
    "â": "“",
    "â": "”",
    "â¦": "…",
    "Â ": " ",
    "Â": "",
}


def clean_text(s: str) -> str:
    for bad, good in _MOJIBAKE.items():
        s = s.replace(bad, good)
    return s


# ----------------------------- LLM call -----------------------------

_last_call_ts = 0.0


def _pace():
    global _last_call_ts
    elapsed = time.time() - _last_call_ts
    if elapsed < MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)
    _last_call_ts = time.time()


class TruncatedResponse(Exception):
    """Gemini hit max_output_tokens before finishing the JSON."""


def transform_with_gemini(client: genai.Client, source_text: str, source_name: str, module_hint: str | None, debug_dir: Path | None = None) -> dict[str, Any]:
    user_msg = (
        f"Source filename: {source_name}\n"
        f"Module hint (may be empty): {module_hint or ''}\n\n"
        f"--- BEGIN DOCUMENT ---\n{source_text}\n--- END DOCUMENT ---"
    )

    last_err: Exception | None = None
    last_raw: str = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _pace()
            resp = client.models.generate_content(
                model=MODEL,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    temperature=0.2,
                ),
            )

            finish_reason = ""
            try:
                finish_reason = str(resp.candidates[0].finish_reason)
            except (AttributeError, IndexError):
                pass

            last_raw = (resp.text or "").strip()

            if "MAX_TOKENS" in finish_reason:
                raise TruncatedResponse(
                    f"Gemini hit MAX_OUTPUT_TOKENS={MAX_OUTPUT_TOKENS}. "
                    f"Doc is too large for one call — raise MAX_OUTPUT_TOKENS (up to 65536) or split the source doc."
                )
            if "SAFETY" in finish_reason or "RECITATION" in finish_reason:
                raise RuntimeError(f"Gemini stopped due to {finish_reason}; response unusable.")

            return _extract_json(last_raw)
        except (APIError, json.JSONDecodeError, TruncatedResponse) as e:
            last_err = e
            # Save raw for inspection if we have it
            if debug_dir and last_raw:
                debug_dir.mkdir(parents=True, exist_ok=True)
                (debug_dir / f"{Path(source_name).stem}.attempt{attempt}.raw.txt").write_text(last_raw, encoding="utf-8")
            wait = 2 ** attempt
            print(f"  ! attempt {attempt} failed ({e.__class__.__name__}: {e}); retry in {wait}s", file=sys.stderr)
            if isinstance(e, TruncatedResponse):
                # Retrying won't help — bigger budget needed.
                break
            time.sleep(wait)
    raise RuntimeError(f"Gemini transform failed after {MAX_RETRIES} attempts: {last_err}")


def _extract_json(raw: str) -> dict[str, Any]:
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("no JSON object found", raw, 0)
    return json.loads(raw[start : end + 1])


# ----------------------------- markdown renderer -----------------------------

def render_markdown(data: dict[str, Any]) -> str:
    doc = data.get("doc", {})
    chunks = data.get("chunks", [])

    out: list[str] = []
    out.append(f"# {doc.get('title', 'Untitled')}\n")
    if doc.get("module"):
        out.append(f"**Module:** {doc['module']}  ")
    if doc.get("tags"):
        out.append(f"**Tags:** {', '.join(doc['tags'])}\n")
    out.append("")

    if doc.get("summary"):
        out.append("## Overview\n")
        out.append(doc["summary"] + "\n")

    if doc.get("prerequisites"):
        out.append("## Prerequisites\n")
        for p in doc["prerequisites"]:
            if isinstance(p, dict):
                out.append(f"- **{p.get('name', '')}** — {p.get('description', '')}")
            else:
                out.append(f"- {p}")
        out.append("")

    for ch in chunks:
        out.append(f"## {ch.get('feature_name', ch.get('id', 'Feature'))}\n")
        out.append(f"<!-- id: {ch.get('id', '')} | category: {ch.get('category', '')} -->\n")

        if ch.get("what_it_does"):
            out.append("**What it does**\n")
            out.append(ch["what_it_does"] + "\n")

        if ch.get("why_it_matters"):
            out.append("**Why it matters**\n")
            out.append(ch["why_it_matters"] + "\n")

        if ch.get("how_to_use"):
            out.append("**How to use**\n")
            for i, step in enumerate(ch["how_to_use"], 1):
                out.append(f"{i}. {step}")
            out.append("")

        if ch.get("examples"):
            out.append("**Examples**\n")
            for ex in ch["examples"]:
                out.append(f"- {ex}")
            out.append("")

        if ch.get("user_questions"):
            out.append("**Questions this answers**\n")
            for q in ch["user_questions"]:
                out.append(f"- {q}")
            out.append("")

        if ch.get("keywords"):
            out.append(f"**Keywords:** {', '.join(ch['keywords'])}\n")
        if ch.get("synonyms"):
            out.append(f"**Synonyms:** {', '.join(ch['synonyms'])}\n")
        if ch.get("related_features"):
            out.append(f"**Related:** {', '.join(ch['related_features'])}\n")
        if ch.get("tags"):
            out.append(f"**Tags:** {', '.join(ch['tags'])}\n")
        out.append("---\n")

    return "\n".join(out)


# ----------------------------- IO -----------------------------

def gather_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.rglob("*.md"))
    raise FileNotFoundError(input_path)


_ILLEGAL_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _safe_filename_part(s: str) -> str:
    s = _ILLEGAL_FS_CHARS.sub("_", s).strip(" .")
    return re.sub(r"\s+", " ", s)


def process_one(src: Path, out_dir: Path, client: genai.Client, module_hint: str | None) -> None:
    print(f"-> {src.name}")
    raw = clean_text(src.read_text(encoding="utf-8", errors="replace"))
    debug_dir = out_dir / "_debug"
    data = transform_with_gemini(client, raw, src.name, module_hint, debug_dir=debug_dir)

    module = (data.get("doc", {}).get("module") or module_hint or "").strip()
    stem = src.stem  # keep spaces
    base = f"{stem} - {_safe_filename_part(module)}" if module else stem

    json_path = out_dir / f"{base}.json"
    md_path = out_dir / f"{base}.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")
    n_chunks = len(data.get("chunks", []))
    print(f"   wrote {json_path.name} + {md_path.name}  ({n_chunks} chunks)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert Markdown docs to AI-search-ready JSON + cleaned MD (Gemini backend).")
    ap.add_argument("input", nargs="?", default=DEFAULT_INPUT, help=f"Markdown file or folder (default: {DEFAULT_INPUT!r})")
    ap.add_argument("-o", "--out", default=DEFAULT_OUTPUT, help=f"Output folder (default: {DEFAULT_OUTPUT!r})")
    ap.add_argument("-m", "--module", default=DEFAULT_MODULE, help="Optional module-name hint")
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: set GEMINI_API_KEY first.  Get a free key at https://aistudio.google.com/apikey", file=sys.stderr)
        return 1

    in_path = Path(args.input)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = genai.Client(api_key=api_key)
    files = gather_inputs(in_path)
    if not files:
        print(f"No .md files found under {in_path}", file=sys.stderr)
        return 1

    print(f"Converting {len(files)} file(s) -> {out_dir}  (model: {MODEL})")
    for f in files:
        try:
            process_one(f, out_dir, client, args.module)
        except Exception as e:
            print(f"   FAILED: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
