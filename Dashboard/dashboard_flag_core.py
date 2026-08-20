"""Core data access + join logic for the dashboard/feature-flag status checker.

Combines four data sources:
  1. pipelines.json - per dag_id: which DB tables it produces, and which
     feature flags gate it.
  2. Zoho Analytics ("Zoho/zoho dashboard dependent tabels.py" logic) - each
     dag's output table exists as a Zoho "Table" view; its `/dependents` API
     tells us which Dashboard views are built on top of that table. That's
     the real dag -> dashboard link (there's no shared ID otherwise: pipelines
     use dag_id, the embed table uses report_name/view_id).
  3. Central config DB (digii-configuration-db / configurations) - which
     dashboards are embedded for which tenant (analytics_tenant_module_report,
     numeric tenant_id/view_id/workspace_id).
  4. Each tenant DB's own `college` table (maps tenant schema -> the numeric
     tenant_id used above) and college_feature_flag/feature tables (which
     flags are open/closed for that tenant).

Step 2 is expensive (Zoho API calls) so its result - workspace_id -> {view_id:
{dashboard_name, source_tables, feature_flags}} - is cached to
dashboard_view_flag_map.json via rebuild_dashboard_view_flag_map(). Steps
1/3/4 are cheap DB reads done live.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

try:
    import mysql.connector
except ImportError as exc:  # pragma: no cover
    mysql = None
    _mysql_import_error = exc
else:
    _mysql_import_error = None

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_env import get_db_config, list_schemas  # noqa: F401  (list_schemas re-exported for UI)

REPO_ROOT = Path(__file__).resolve().parent
DASHBOARD_MAP_CACHE_PATH = REPO_ROOT / "dashboard_view_flag_map.json"
PIPELINES_JSON_PATH = Path(r"C:\Users\suraj\OneDrive\Desktop\pipelines.json")

CENTRAL_DB_CONFIG = {
    "host": "digii-configuration-db.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
    "user": "read_user",
    "password": "apt2^yvT",
    "database": "configurations",
}

EMBED_QUERY = """
SELECT t1.id AS atmr_id, module, report_id, report_name, t1.active,
       workspace_id, view_id, tenant_id
FROM analytics_tenant_module_report t1
LEFT JOIN analytics_report ar ON ar.id = t1.report_id
WHERE ACTIVE = 1
"""

FLAG_QUERY = """
SELECT t2.feature, t2.default_name, t1.feature_custom_name, t2.description, t1.status
FROM college_feature_flag t1
LEFT JOIN feature t2 ON t1.feature_id = t2.id
"""

ZOHO_ACCOUNTS_URL = "https://accounts.zoho.in/oauth/v2/token"
ZOHO_VIEWS_URL = "https://analyticsapi.zoho.in/restapi/v2/workspaces/{workspace_id}/views"
ZOHO_DEPENDENTS_URL = "https://analyticsapi.zoho.in/restapi/v2/workspaces/{workspace_id}/views/{view_id}/dependents"

UNMAPPED = "UNMAPPED (no dag traced to this dashboard - verify manually)"
NOT_EMBEDDED = "NOT EMBEDDED"
READY = "READY (embedded, flags OK)"
FLAGS_NOT_ENABLED = "FLAGS NOT ENABLED"
FLAGS_UNKNOWN = "FLAG NOT FOUND ON TENANT"


def _require_mysql():
    if _mysql_import_error:
        raise RuntimeError(f"mysql-connector-python is required.\n{_mysql_import_error}")


# ---------------------------------------------------------------------------
# 1. pipelines.json -> table_name -> (feature_flags, dag_ids), and per-tenant
#    dag scheduling (dag_id.enabled), in one pass over the file.
# ---------------------------------------------------------------------------

def _split_flag_values(raw):
    if raw is None:
        return []
    parts = re.split(r"[;,]", str(raw))
    return [p.strip() for p in parts if p.strip()]


def build_pipelines_maps(pipelines_json_path: Path = PIPELINES_JSON_PATH) -> tuple[dict, dict, dict]:
    """One pass over pipelines.json ->
    (table_flag_map, table_dag_map, tenant_dag_schedule)

    table_flag_map: table_name -> sorted [feature_flags], unioned across every dag_id producing it
    table_dag_map:  table_name -> sorted [dag_ids] that produce it
    tenant_dag_schedule: {tenant_id: {dag_id: enabled_bool}} (tenant_id is pipelines.json's short form,
        e.g. "ace" - matches the schema short name accepted by db_env.get_db_config)
    """
    with open(pipelines_json_path, encoding="utf-8") as f:
        payload = json.load(f)
    records = payload["results"] if isinstance(payload, dict) and "results" in payload else payload

    table_flags: dict[str, set] = {}
    table_dags: dict[str, set] = {}
    tenant_dag_schedule: dict[str, dict] = {}

    for rec in records:
        tenant = str(rec.get("tenant_id", "")).strip()
        dag_id = str(rec.get("dag_id", "")).strip()
        tables = rec.get("tables") or []
        flags = []
        for item in rec.get("feature_flags") or []:
            flags.extend(_split_flag_values(item))

        for table in tables:
            table_flags.setdefault(table, set()).update(flags)
            if dag_id:
                table_dags.setdefault(table, set()).add(dag_id)

        if tenant and dag_id:
            tenant_dag_schedule.setdefault(tenant, {})[dag_id] = bool(rec.get("enabled"))

    table_flag_map = {t: sorted(f) for t, f in table_flags.items()}
    table_dag_map = {t: sorted(d) for t, d in table_dags.items()}
    return table_flag_map, table_dag_map, tenant_dag_schedule


_pipelines_cache: tuple | None = None


def get_pipelines_maps(pipelines_json_path: Path = PIPELINES_JSON_PATH, force_reload: bool = False) -> tuple[dict, dict, dict]:
    """Cached wrapper around build_pipelines_maps() - pipelines.json is ~2MB, no need to re-parse it per tenant."""
    global _pipelines_cache
    if _pipelines_cache is None or force_reload:
        _pipelines_cache = build_pipelines_maps(pipelines_json_path)
    return _pipelines_cache


def schema_to_pipeline_tenant_id(schema: str) -> str:
    """db_credentials.json schemas are 'collpoll_<short>'; pipelines.json tenant_id is just '<short>'."""
    prefix = "collpoll_"
    return schema[len(prefix):] if schema.startswith(prefix) else schema


# ---------------------------------------------------------------------------
# 2. Zoho Analytics - table view -> dependent dashboards
# ---------------------------------------------------------------------------

def get_zoho_credentials() -> dict:
    """Pull client_id/secret/refresh_token/org_id from the central zoho_analytics_token table."""
    _require_mysql()
    conn = mysql.connector.connect(**CENTRAL_DB_CONFIG, connection_timeout=60)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT client_id, client_secret, refresh_token, organization_id "
            "FROM zoho_analytics_token WHERE token_type = 'URL_GENERATION_TOKEN' "
            "ORDER BY modified_timestamp DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("No URL_GENERATION_TOKEN row found in zoho_analytics_token.")
        return row
    finally:
        conn.close()


def get_zoho_access_token() -> tuple[str, str]:
    """-> (access_token, organization_id), refreshed from the stored refresh_token."""
    creds = get_zoho_credentials()
    resp = requests.post(ZOHO_ACCOUNTS_URL, data={
        "refresh_token": creds["refresh_token"],
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "grant_type": "refresh_token",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"Zoho token refresh failed: {data}")
    return data["access_token"], creds["organization_id"]


def _zoho_headers(token: str, org_id: str) -> dict:
    return {"Authorization": f"Zoho-oauthtoken {token}", "ZANALYTICS-ORGID": org_id}


def fetch_workspace_views(workspace_id: str, token: str, org_id: str) -> list:
    url = ZOHO_VIEWS_URL.format(workspace_id=workspace_id)
    resp = requests.get(url, headers=_zoho_headers(token, org_id), timeout=30)
    resp.raise_for_status()
    return resp.json()["data"]["views"]


def fetch_view_dependents(workspace_id: str, view_id: str, token: str, org_id: str,
                           retries: int = 3, retry_delay: float = 1.5) -> list:
    """Zoho's dependents endpoint intermittently 400s under load; a short retry clears most of these."""
    url = ZOHO_DEPENDENTS_URL.format(workspace_id=workspace_id, view_id=view_id)
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=_zoho_headers(token, org_id), timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return data.get("views", []) if isinstance(data, dict) else []
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(retry_delay)
    raise last_exc


def build_workspace_dashboard_flag_map(workspace_id: str, table_flag_map: dict, table_dag_map: dict,
                                        token: str, org_id: str, delay: float = 0.4, log_cb=None) -> dict:
    """view_id -> {dashboard_name, source_tables, source_dags, feature_flags} for one Zoho workspace."""
    views = fetch_workspace_views(workspace_id, token, org_id)
    table_views = [v for v in views if str(v.get("viewType", "")).lower() == "table"]

    dashboards: dict[str, dict] = {}
    matched = 0
    failed = []
    for i, v in enumerate(table_views, start=1):
        raw_name = v.get("viewName", "")
        table_name = raw_name.rsplit(".", 1)[-1]
        flags = table_flag_map.get(table_name)
        if not flags:
            continue
        matched += 1
        try:
            deps = fetch_view_dependents(workspace_id, v["viewId"], token, org_id)
        except requests.exceptions.RequestException as exc:
            failed.append(raw_name)
            if log_cb:
                log_cb(f"  skipped table view {raw_name} ({v.get('viewId')}) after retries: {exc}")
            time.sleep(delay)
            continue
        for dep in deps:
            if str(dep.get("viewType", "")).lower() != "dashboard":
                continue
            dash_id = str(dep.get("viewId", ""))
            entry = dashboards.setdefault(dash_id, {
                "dashboard_name": dep.get("viewName", ""),
                "source_tables": set(),
                "source_dags": set(),
                "feature_flags": set(),
            })
            entry["source_tables"].add(table_name)
            entry["source_dags"].update(table_dag_map.get(table_name, []))
            entry["feature_flags"].update(flags)
        time.sleep(delay)

    if log_cb:
        log_cb(f"  workspace {workspace_id}: {matched}/{len(table_views)} table view(s) matched pipelines.json, "
               f"{len(dashboards)} dashboard(s) resolved, {len(failed)} table(s) failed after retries")

    return {
        dash_id: {
            "dashboard_name": info["dashboard_name"],
            "source_tables": sorted(info["source_tables"]),
            "source_dags": sorted(info["source_dags"]),
            "feature_flags": sorted(info["feature_flags"]),
        }
        for dash_id, info in dashboards.items()
    }


def rebuild_dashboard_view_flag_map(workspace_ids, pipelines_json_path: Path = PIPELINES_JSON_PATH, log_cb=None) -> dict:
    """Rebuild + cache the workspace_id -> view_id -> flags map. Hits the Zoho API - slow, run on demand."""
    if log_cb:
        log_cb(f"Loading pipelines.json ({pipelines_json_path})...")
    table_flag_map, table_dag_map, _ = get_pipelines_maps(pipelines_json_path, force_reload=True)
    if log_cb:
        log_cb(f"{len(table_flag_map)} distinct output table(s) found across all dags.")

    if log_cb:
        log_cb("Refreshing Zoho access token...")
    token, org_id = get_zoho_access_token()

    full_map = {}
    for ws in workspace_ids:
        ws = str(ws)
        if log_cb:
            log_cb(f"Workspace {ws}: fetching views...")
        try:
            full_map[ws] = build_workspace_dashboard_flag_map(
                ws, table_flag_map, table_dag_map, token, org_id, log_cb=log_cb,
            )
        except requests.exceptions.RequestException as exc:
            if log_cb:
                log_cb(f"  workspace {ws}: skipped - {exc}")

    with open(DASHBOARD_MAP_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(full_map, f, indent=2)
    if log_cb:
        log_cb(f"Saved mapping to {DASHBOARD_MAP_CACHE_PATH}")

    return full_map


def load_dashboard_view_flag_map() -> dict:
    if not DASHBOARD_MAP_CACHE_PATH.exists():
        return {}
    with open(DASHBOARD_MAP_CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 3 & 4. Central embed data + per-tenant flags
# ---------------------------------------------------------------------------

def fetch_embedded_dashboards() -> pd.DataFrame:
    """One-shot pull of every currently-embedded dashboard, across all tenants."""
    _require_mysql()
    conn = mysql.connector.connect(**CENTRAL_DB_CONFIG, connection_timeout=60)
    try:
        return pd.read_sql(EMBED_QUERY, conn)
    finally:
        conn.close()


def fetch_college_id(schema: str) -> int | None:
    """The numeric tenant_id (college.college_id) for a tenant schema."""
    _require_mysql()
    cfg = get_db_config(schema)
    conn = mysql.connector.connect(
        host=cfg["host"], user=cfg["user"], password=cfg["password"],
        database=cfg["database"], connection_timeout=60,
    )
    try:
        cur = conn.cursor()
        cur.execute("SELECT college_id FROM college LIMIT 1")
        row = cur.fetchone()
        return int(row[0]) if row else None
    finally:
        conn.close()


def fetch_tenant_flags(schema: str) -> dict:
    """feature -> status ('open'/'closed') for one tenant."""
    _require_mysql()
    cfg = get_db_config(schema)
    conn = mysql.connector.connect(
        host=cfg["host"], user=cfg["user"], password=cfg["password"],
        database=cfg["database"], connection_timeout=60,
    )
    try:
        df = pd.read_sql(FLAG_QUERY, conn)
    finally:
        conn.close()
    return dict(zip(df["feature"], df["status"].str.lower()))


# ---------------------------------------------------------------------------
# Join it all together
# ---------------------------------------------------------------------------

def _evaluate_flags(required_flags, tenant_flags: dict):
    """-> (flags_detail_str, all_open: bool, any_unknown: bool)"""
    if not required_flags:
        return "", False, False

    parts = []
    all_open = True
    any_unknown = False
    for flag in required_flags:
        status = tenant_flags.get(flag)
        if status is None:
            parts.append(f"{flag}=NOT_FOUND")
            all_open = False
            any_unknown = True
        else:
            parts.append(f"{flag}={status}")
            if status != "open":
                all_open = False
    return ", ".join(parts), all_open, any_unknown


def _evaluate_pipeline_schedule(source_dags, tenant_pipeline_id: str, tenant_dag_schedule: dict) -> str:
    """-> 'dag_id=Yes/No/NO_RECORD, ...' - whether each source dag is currently scheduled for this tenant."""
    if not source_dags:
        return ""
    dag_status = tenant_dag_schedule.get(tenant_pipeline_id, {})
    parts = []
    for dag in source_dags:
        enabled = dag_status.get(dag)
        parts.append(f"{dag}=NO_RECORD" if enabled is None else f"{dag}={'Yes' if enabled else 'No'}")
    return ", ".join(parts)


def build_tenant_dashboard_report(schema: str, embed_df: pd.DataFrame, dashboard_map: dict,
                                   college_id: int | None = None, tenant_flags: dict | None = None,
                                   tenant_dag_schedule: dict | None = None) -> pd.DataFrame:
    """Per-dashboard status for one tenant. Fetches college_id/flags/pipeline-schedule if not supplied."""
    if college_id is None:
        college_id = fetch_college_id(schema)
    if tenant_flags is None:
        tenant_flags = fetch_tenant_flags(schema)
    if tenant_dag_schedule is None:
        _, _, tenant_dag_schedule = get_pipelines_maps()
    tenant_pipeline_id = schema_to_pipeline_tenant_id(schema)

    tenant_dashboards = embed_df[embed_df["tenant_id"] == college_id] if college_id is not None else embed_df.iloc[0:0]

    rows = []
    for _, d in tenant_dashboards.iterrows():
        ws = str(d["workspace_id"])
        view_id = str(d["view_id"])
        info = dashboard_map.get(ws, {}).get(view_id)
        required_flags = info["feature_flags"] if info else None
        source_tables = ", ".join(info["source_tables"]) if info else ""
        source_dags = info.get("source_dags") if info else None

        flags_detail, all_open, any_unknown = _evaluate_flags(required_flags, tenant_flags)
        pipelines_scheduled = _evaluate_pipeline_schedule(source_dags, tenant_pipeline_id, tenant_dag_schedule)

        if info is None:
            status = UNMAPPED
        elif not required_flags:
            status = READY
        elif any_unknown:
            status = FLAGS_UNKNOWN
        elif all_open:
            status = READY
        else:
            status = FLAGS_NOT_ENABLED

        rows.append({
            "tenant_schema": schema,
            "tenant_id": college_id,
            "module": d["module"],
            "report_name": d["report_name"],
            "workspace_id": ws,
            "view_id": view_id,
            "embedded": "Yes",
            "source_tables": source_tables,
            "required_flags": ", ".join(required_flags) if required_flags else "",
            "flags_detail": flags_detail,
            "pipelines_scheduled": pipelines_scheduled,
            "status": status,
        })

    return pd.DataFrame(rows, columns=[
        "tenant_schema", "tenant_id", "module", "report_name", "workspace_id", "view_id",
        "embedded", "source_tables", "required_flags", "flags_detail", "pipelines_scheduled", "status",
    ])


def build_all_tenants_report(schemas, embed_df: pd.DataFrame, dashboard_map: dict, progress_cb=None) -> tuple[pd.DataFrame, list]:
    """Loop build_tenant_dashboard_report() across many tenants.

    progress_cb(index, total, schema) is called before each tenant, if given.
    Returns (combined_df, errors) where errors is a list of (schema, exception) pairs
    for tenants that couldn't be reached - they're skipped, not fatal.
    """
    frames = []
    errors = []
    total = len(schemas)
    for i, schema in enumerate(schemas, start=1):
        if progress_cb:
            progress_cb(i, total, schema)
        try:
            frames.append(build_tenant_dashboard_report(schema, embed_df, dashboard_map))
        except Exception as exc:  # noqa: BLE001 - one bad tenant shouldn't kill the batch
            errors.append((schema, exc))

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return combined, errors
