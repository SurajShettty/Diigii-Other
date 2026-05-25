"""
doc_to_ai_search.py
-------------------
Convert Digii product documentation (Markdown) into AI-search-compatible
structured JSON + a cleaned, keyword-rich Markdown version for use by a
RAG chatbot.

API-FREE single-run pipeline. The LLM step is performed by shelling out
to the local `claude` CLI (Claude Code), which uses your existing Claude
login — no ANTHROPIC_API_KEY needed.

Pipeline:
    .md (raw)  ->  cleanup mojibake
               ->  `claude -p` with SYSTEM_PROMPT  ->  structured JSON
                                                  ->  rendered Markdown

Usage:
    1. Make sure the `claude` CLI is installed and logged in:
           npm install -g @anthropic-ai/claude-code
           claude            (run once to authenticate, then exit)
    2. Edit INPUT_PATH / OUTPUT_DIR / MODULE_HINT below.
    3. python doc_to_ai_search.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# ----------------------------- config (edit here) -----------------------------

INPUT_PATH = r"c:\Users\suraj\Downloads\My Python\Digii Other\Documentations"
OUTPUT_DIR = r"c:\Users\suraj\Downloads\My Python\Digii Other\ai_docs_out"
MODULE_HINT: str | None = None

CLAUDE_MODEL = "sonnet"           # alias; CLI resolves to latest Sonnet
CLI_TIMEOUT_SEC = 600
MAX_RETRIES = 2
MAX_WORKERS = 4                   # parallel `claude` processes; tune for your machine + rate limits

SYSTEM_PROMPT = """You are a documentation transformer for a RAG (retrieval-augmented generation) chatbot that answers user questions about the Digii campus-management platform (LMS / admin / HR / academics).

Your job: take a raw Markdown document describing features and emit ONE JSON object with rich, search-optimised content.

OUTPUT SCHEMA (return JSON only — no prose, no code fences):
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
   - 'â' or 'â' followed by garbage -> em dash '—'
   - 'â' -> '’' apostrophe
   - 'â' / 'â' -> curly quotes
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
9. Return ONLY the JSON object. No commentary, no markdown fences."""


# ----------------------------- text cleanup -----------------------------

_MOJIBAKE = {
    "â": "—",
    "â": "–",
    "â": "’",
    "â": "‘",
    "â": "“",
    "â": "”",
    "â¦": "…",
    "Â ": " ",
    "Â": "",
}


def clean_text(s: str) -> str:
    for bad, good in _MOJIBAKE.items():
        s = s.replace(bad, good)
    return s


# ----------------------------- claude CLI call -----------------------------

def _find_claude_cli() -> str:
    # On Windows, npm installs claude.cmd / .ps1 / .exe. shutil.which finds the first one.
    for name in ("claude.cmd", "claude.exe", "claude"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(
        "`claude` CLI not found on PATH. Install with:\n"
        "    npm install -g @anthropic-ai/claude-code\n"
        "then run `claude` once to authenticate."
    )


def transform_with_claude_cli(
    claude_path: str,
    sys_prompt_file: str,
    source_text: str,
    source_name: str,
    module_hint: str | None,
) -> dict[str, Any]:
    user_msg = (
        f"Source filename: {source_name}\n"
        f"Module hint (may be empty): {module_hint or ''}\n\n"
        f"--- BEGIN DOCUMENT ---\n{source_text}\n--- END DOCUMENT ---"
    )

    cmd = [
        claude_path,
        "-p",
        "--model", CLAUDE_MODEL,
        "--system-prompt-file", sys_prompt_file,
        "--output-format", "text",
    ]

    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                cmd,
                input=user_msg,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=CLI_TIMEOUT_SEC,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"claude CLI exit {result.returncode}: {result.stderr.strip()[:500]}"
                )
            return _extract_json(result.stdout)
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  ! attempt {attempt} failed ({e.__class__.__name__}); retry in {wait}s",
                  file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"claude CLI transform failed after {MAX_RETRIES} attempts: {last_err}")


def _extract_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
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


_print_lock = threading.Lock()


def _log(msg: str, *, err: bool = False) -> None:
    with _print_lock:
        print(msg, file=sys.stderr if err else sys.stdout, flush=True)


def process_one(
    src: Path,
    out_dir: Path,
    claude_path: str,
    sys_prompt_file: str,
    module_hint: str | None,
) -> tuple[Path, bool, str]:
    _log(f"-> {src.name}")
    try:
        raw = clean_text(src.read_text(encoding="utf-8", errors="replace"))
        data = transform_with_claude_cli(
            claude_path, sys_prompt_file, raw, src.name, module_hint
        )

        base = src.stem.replace(" ", "_")
        json_path = out_dir / f"{base}.json"
        md_path = out_dir / f"{base}.md"

        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(render_markdown(data), encoding="utf-8")
        n_chunks = len(data.get("chunks", []))
        _log(f"   ok  {src.name}  ->  {json_path.name} + {md_path.name}  ({n_chunks} chunks)")
        return (src, True, "")
    except Exception as e:
        _log(f"   FAIL {src.name}: {e}", err=True)
        return (src, False, str(e))


def main() -> int:
    try:
        claude_path = _find_claude_cli()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    in_path = Path(INPUT_PATH)
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = gather_inputs(in_path)
    if not files:
        print(f"No .md files found under {in_path}", file=sys.stderr)
        return 1

    # write SYSTEM_PROMPT to a temp file once and reuse across calls
    fd, sys_prompt_file = tempfile.mkstemp(prefix="digii_sys_", suffix=".txt", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(SYSTEM_PROMPT)

        workers = max(1, min(MAX_WORKERS, len(files)))
        print(
            f"Converting {len(files)} file(s) -> {out_dir}  "
            f"(model: {CLAUDE_MODEL}, workers: {workers})"
        )
        failed = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    process_one, f, out_dir, claude_path, sys_prompt_file, MODULE_HINT
                )
                for f in files
            ]
            for fut in as_completed(futures):
                _src, ok, _err = fut.result()
                if not ok:
                    failed += 1
        if failed:
            print(f"{failed} file(s) failed.", file=sys.stderr)
            return 2
        return 0
    finally:
        try:
            os.unlink(sys_prompt_file)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
