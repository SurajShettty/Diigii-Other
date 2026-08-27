"""Audit log viewer.

Browses `audit_log` joined to `audit_log_status` (on audit_log.id =
audit_log_status.audit_log_id) for any tenant schema. Both tables store
change data as messy JSON strings in longtext columns — this UI parses and
pretty-prints that JSON, and diffs previous_value vs current_value so you
can actually see what changed instead of reading raw text blobs.

Filters: entity, action, ukid, entity_primary_key, audit log id, date
range, free-text keyword search across the JSON blobs, and an "only
failures" toggle (looks for "success":false / errorMessage in the JSON,
which is how most write-actions record failures in this schema).

Run:
    python audit_log_viewer.py
Then open http://127.0.0.1:5000 in a browser.
"""

import sys
from pathlib import Path

import mysql.connector
from flask import Flask, jsonify, render_template_string, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_env import get_db_config, list_schemas

app = Flask(__name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Audit Log Viewer</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 0; background: #f5f6f8; color: #1c1e21; }
    header { background: #1f2937; color: #fff; padding: 14px 24px; }
    header h1 { margin: 0; font-size: 18px; font-weight: 600; }
    .bar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 12px 24px; background: #fff; border-bottom: 1px solid #e2e5e9; }
    .bar .grp { display: flex; flex-direction: column; gap: 2px; }
    .bar label { font-size: 11px; color: #6b7280; }
    input, button, select { font-size: 13px; padding: 7px 10px; border: 1px solid #cfd4da; border-radius: 6px; }
    select { background: #fff; cursor: pointer; }
    input { min-width: 120px; }
    #schema { min-width: 220px; }
    #keyword { min-width: 200px; }
    button { background: #2563eb; color: #fff; border-color: #2563eb; cursor: pointer; font-weight: 500; }
    button:hover { background: #1d4ed8; }
    button.secondary { background: #fff; color: #1c1e21; border-color: #cfd4da; }
    button.secondary:hover { background: #f0f2f5; }
    .chk { flex-direction: row !important; align-items: center; gap: 6px !important; }
    .chk label { font-size: 13px; color: #1c1e21; }
    #status { padding: 6px 24px; font-size: 13px; color: #555; }
    #status.err { color: #b91c1c; }
    .layout { display: flex; gap: 0; height: calc(100vh - 128px); }
    .listcol { flex: 1 1 55%; overflow: auto; border-right: 1px solid #e2e5e9; }
    .detailcol { flex: 1 1 45%; overflow: auto; padding: 16px 20px; background: #fff; }
    table { border-collapse: collapse; width: 100%; background: #fff; font-size: 12.5px; }
    th, td { border-bottom: 1px solid #eef0f2; padding: 6px 10px; text-align: left; white-space: nowrap; }
    th { background: #f0f2f5; position: sticky; top: 0; z-index: 1; }
    tr.row { cursor: pointer; }
    tr.row:hover td { background: #eef4ff; }
    tr.row.sel td { background: #dbe7ff; }
    .flag { display: inline-block; width: 9px; height: 9px; border-radius: 50%; }
    .flag.fail { background: #dc2626; }
    .flag.ok { background: #16a34a; }
    .flag.na { background: #d1d5db; }
    .pager { display: flex; gap: 8px; align-items: center; padding: 10px 24px; background: #fff; border-top: 1px solid #e2e5e9; font-size: 13px; }
    .pager span { color: #555; }
    .section { margin-bottom: 18px; }
    .section h3 { margin: 0 0 6px; font-size: 13px; text-transform: uppercase; letter-spacing: .03em; color: #6b7280; }
    .meta { font-size: 13px; line-height: 1.7; margin-bottom: 14px; }
    .meta b { color: #111827; }
    .pill { display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 4px; padding: 1px 8px; font-size: 12px; margin-left: 4px; }
    pre.json { background: #0f172a; color: #e2e8f0; padding: 10px 12px; border-radius: 6px; font-size: 12.5px; overflow-x: auto; white-space: pre-wrap; word-break: break-word; margin: 0; }
    pre.json .k { color: #93c5fd; }
    pre.json .s { color: #86efac; }
    pre.json .n { color: #fca5a5; }
    pre.json .b { color: #fcd34d; }
    pre.json .z { color: #9ca3af; }
    .diffline { display: block; padding: 0 4px; }
    .diffline.add { background: rgba(22,163,74,.22); }
    .diffline.del { background: rgba(220,38,38,.22); text-decoration: line-through; opacity: .85; }
    .empty { color: #9ca3af; font-size: 13px; font-style: italic; }
    .placeholder { padding: 40px 20px; color: #9ca3af; font-size: 14px; text-align: center; }
    .copybtn { font-size: 11px; padding: 2px 8px; margin-left: 8px; }
  </style>
</head>
<body>
  <header><h1>Audit Log Viewer &mdash; audit_log ⋈ audit_log_status</h1></header>
  <div class="bar">
    <div class="grp"><label>Schema</label>
      <select id="schema">
        <option value="">Select schema…</option>
        {% for s in schemas %}<option value="{{ s }}">{{ s }}</option>{% endfor %}
      </select>
    </div>
    <div class="grp"><label>Entity</label><input id="entity" list="entities" placeholder="e.g. QUIZ"></div>
    <div class="grp"><label>Action</label><select id="action"><option value="">All actions</option></select></div>
    <div class="grp"><label>UKID</label><input id="ukid" style="min-width:80px" placeholder="user id"></div>
    <div class="grp"><label>Entity PK</label><input id="epk" style="min-width:90px" placeholder="record id"></div>
    <div class="grp"><label>Log ID</label><input id="logid" style="min-width:80px" placeholder="audit id"></div>
    <div class="grp"><label>From</label><input id="from" type="date"></div>
    <div class="grp"><label>To</label><input id="to" type="date"></div>
    <div class="grp"><label>Keyword (searches JSON)</label><input id="keyword" placeholder="text inside previous/current value"></div>
    <div class="grp chk"><input type="checkbox" id="failonly"><label for="failonly">Only failures</label></div>
    <div class="grp"><label>&nbsp;</label>
      <select id="sort"><option value="desc">Newest first</option><option value="asc">Oldest first</option></select>
    </div>
    <div class="grp"><label>&nbsp;</label><button id="search">Search</button></div>
    <div class="grp"><label>&nbsp;</label><button id="clear" class="secondary">Clear</button></div>
  </div>
  <div id="status">Select a schema and click Search.</div>
  <datalist id="entities"></datalist>
  <div class="layout">
    <div class="listcol">
      <table id="tbl">
        <thead><tr><th></th><th>ID</th><th>Timestamp</th><th>Entity</th><th>Entity PK</th><th>Action</th><th>UKID</th></tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
    <div class="detailcol" id="detail"><div class="placeholder">Select a row to view its details.</div></div>
  </div>
  <div class="pager">
    <button id="prev" class="secondary">&larr; Prev</button>
    <span id="pageinfo">&nbsp;</span>
    <button id="next" class="secondary">Next &rarr;</button>
    <select id="pagesize" style="margin-left:12px">
      <option value="25">25 / page</option>
      <option value="50" selected>50 / page</option>
      <option value="100">100 / page</option>
      <option value="250">250 / page</option>
    </select>
  </div>

<script>
const $ = id => document.getElementById(id);
let ROWS = [], TOTAL = 0, PAGE = 0, SELECTED_ID = null;

function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function tryParse(raw) {
  if (raw === null || raw === undefined) return {ok:false, raw: 'NULL'};
  const s = String(raw).trim();
  if (s === '' || s.toLowerCase() === 'null') return {ok:false, raw: 'NULL'};
  try { return {ok:true, val: JSON.parse(s)}; } catch(e) { return {ok:false, raw: s}; }
}

function highlightJSON(str) {
  const escaped = esc(str);
  return escaped.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false)\b|\bnull\b|-?\d+(\.\d+)?([eE][+-]?\d+)?)/g,
    match => {
      let cls = 'n';
      if (/^"/.test(match)) cls = /:$/.test(match) ? 'k' : 's';
      else if (/true|false/.test(match)) cls = 'b';
      else if (/null/.test(match)) cls = 'z';
      return '<span class="' + cls + '">' + match + '</span>';
    });
}

function prettyOrRaw(raw) {
  const p = tryParse(raw);
  if (p.ok) return highlightJSON(JSON.stringify(p.val, null, 2));
  return '<span class="z">' + esc(p.raw) + '</span>';
}

// Simple LCS-based line diff.
function diffLines(a, b) {
  const A = a.split('\n'), B = b.split('\n');
  const n = A.length, m = B.length;
  const dp = Array.from({length: n+1}, () => new Uint16Array(m+1));
  for (let i = n-1; i >= 0; i--)
    for (let j = m-1; j >= 0; j--)
      dp[i][j] = A[i] === B[j] ? dp[i+1][j+1] + 1 : Math.max(dp[i+1][j], dp[i][j+1]);
  const out = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) { out.push({t:'same', l:A[i]}); i++; j++; }
    else if (dp[i+1][j] >= dp[i][j+1]) { out.push({t:'del', l:A[i]}); i++; }
    else { out.push({t:'add', l:B[j]}); j++; }
  }
  while (i < n) { out.push({t:'del', l:A[i++]}); }
  while (j < m) { out.push({t:'add', l:B[j++]}); }
  return out;
}

function renderDiff(prevRaw, currRaw) {
  const pp = tryParse(prevRaw), cp = tryParse(currRaw);
  const prevHasReal = pp.ok || (pp.raw && pp.raw !== 'NULL');
  const currHasReal = cp.ok || (cp.raw && cp.raw !== 'NULL');
  if (!prevHasReal && !currHasReal) return '<div class="empty">No data.</div>';
  if (!prevHasReal) return '<pre class="json">' + prettyOrRaw(currRaw) + '</pre>';
  if (!currHasReal) return '<pre class="json">' + prettyOrRaw(prevRaw) + '</pre>';
  const prevStr = pp.ok ? JSON.stringify(pp.val, null, 2) : pp.raw;
  const currStr = cp.ok ? JSON.stringify(cp.val, null, 2) : cp.raw;
  if (prevStr === currStr) return '<pre class="json">' + prettyOrRaw(currRaw) + '</pre>';
  const lines = diffLines(prevStr, currStr);
  const html = lines.map(d => {
    const cls = d.t === 'add' ? 'add' : d.t === 'del' ? 'del' : '';
    const prefix = d.t === 'add' ? '+ ' : d.t === 'del' ? '- ' : '  ';
    return '<span class="diffline ' + cls + '">' + esc(prefix) + highlightJSON(d.l) + '</span>';
  }).join('\n');
  return '<pre class="json">' + html + '</pre>';
}

function judgeStatus(row) {
  const blob = (row.status_current_value || '') + (row.current_value || '');
  if (/"success"\s*:\s*false/.test(blob) || /errorMessage/.test(blob)) return 'fail';
  if (/"success"\s*:\s*true/.test(blob)) return 'ok';
  return 'na';
}

function setStatus(m, err) { const s = $('status'); s.textContent = m; s.className = err ? 'err' : ''; }

function collectFilters() {
  return {
    schema: $('schema').value.trim(),
    entity: $('entity').value.trim(),
    action: $('action').value.trim(),
    ukid: $('ukid').value.trim(),
    epk: $('epk').value.trim(),
    logid: $('logid').value.trim(),
    from: $('from').value,
    to: $('to').value,
    keyword: $('keyword').value.trim(),
    failonly: $('failonly').checked ? '1' : '',
    sort: $('sort').value,
    page: PAGE,
    page_size: $('pagesize').value,
  };
}

async function search(resetPage) {
  const schema = $('schema').value.trim();
  if (!schema) { setStatus('Please select a schema.', true); return; }
  if (resetPage) PAGE = 0;
  const f = collectFilters();
  const qs = new URLSearchParams(f).toString();
  setStatus('Loading…');
  $('search').disabled = true;
  try {
    const r = await fetch('/api/search?' + qs);
    const data = await r.json();
    if (!r.ok) { setStatus(data.error || 'Request failed.', true); renderRows([]); return; }
    ROWS = data.rows; TOTAL = data.total;
    renderRows(ROWS);
    const start = ROWS.length ? PAGE * data.page_size + 1 : 0;
    const end = PAGE * data.page_size + ROWS.length;
    $('pageinfo').textContent = TOTAL ? (start + '-' + end + ' of ' + TOTAL) : '0 of 0';
    setStatus('Loaded ' + ROWS.length + ' row(s) from ' + data.schema + '.');
    loadLookups(schema);
  } catch (e) {
    setStatus('Error: ' + e, true);
  } finally {
    $('search').disabled = false;
  }
}

function renderRows(rows) {
  const tbody = $('tbody');
  tbody.innerHTML = rows.map(row => {
    const st = judgeStatus(row);
    return '<tr class="row" data-id="' + row.id + '">' +
      '<td><span class="flag ' + st + '" title="' + st + '"></span></td>' +
      '<td>' + row.id + '</td>' +
      '<td>' + esc(row.timestamp || '') + '</td>' +
      '<td>' + esc(row.entity) + '</td>' +
      '<td>' + esc(row.entity_primary_key) + '</td>' +
      '<td>' + esc(row.action) + '</td>' +
      '<td>' + esc(row.ukid) + '</td>' +
      '</tr>';
  }).join('');
  tbody.querySelectorAll('tr.row').forEach(tr => {
    tr.onclick = () => selectRow(parseInt(tr.dataset.id, 10));
  });
  if (!rows.length) $('detail').innerHTML = '<div class="placeholder">No matching rows.</div>';
}

function selectRow(id) {
  SELECTED_ID = id;
  document.querySelectorAll('tr.row').forEach(tr => tr.classList.toggle('sel', parseInt(tr.dataset.id,10) === id));
  const row = ROWS.find(r => r.id === id);
  if (!row) return;
  const hasStatusRow = row.status_id !== null && row.status_id !== undefined;
  let html = '<div class="meta">';
  html += '<b>Audit ID:</b> ' + row.id + ' &nbsp; <b>Entity:</b> ' + esc(row.entity) + ' <span class="pill">' + esc(row.entity_primary_key) + '</span><br>';
  html += '<b>Action:</b> ' + esc(row.action) + '<br>';
  html += '<b>UKID (actor):</b> ' + esc(row.ukid) + ' &nbsp; <b>Timestamp:</b> ' + esc(row.timestamp) + '</div>';

  html += '<div class="section"><h3>Change (audit_log.previous_value &rarr; current_value)</h3>' +
    renderDiff(row.previous_value, row.current_value) + '</div>';

  if (hasStatusRow) {
    html += '<div class="section"><h3>Status / Result (audit_log_status' +
      (row.status_timestamp ? ' &mdash; ' + esc(row.status_timestamp) : '') + ')</h3>' +
      renderDiff(row.status_previous_value, row.status_current_value) + '</div>';
  } else {
    html += '<div class="section"><h3>Status / Result (audit_log_status)</h3><div class="empty">No matching audit_log_status row.</div></div>';
  }
  $('detail').innerHTML = html;
}

async function loadEntities(schema) {
  try {
    const r = await fetch('/api/entities?schema=' + encodeURIComponent(schema));
    const data = await r.json();
    if (r.ok) $('entities').innerHTML = data.entities.map(e => '<option value="' + esc(e) + '">').join('');
  } catch (e) {}
}

async function loadActions(schema, entity) {
  try {
    const r = await fetch('/api/actions?schema=' + encodeURIComponent(schema) + '&entity=' + encodeURIComponent(entity || ''));
    const data = await r.json();
    if (!r.ok) return;
    const current = $('action').value;
    $('action').innerHTML = '<option value="">All actions</option>' +
      data.actions.map(a => '<option value="' + esc(a) + '">' + esc(a) + '</option>').join('');
    if (data.actions.includes(current)) $('action').value = current;
  } catch (e) {}
}

function loadLookups(schema) {
  loadEntities(schema);
  loadActions(schema, $('entity').value.trim());
}

$('search').onclick = () => search(true);
$('clear').onclick = () => {
  ['entity','ukid','epk','logid','from','to','keyword'].forEach(id => $(id).value = '');
  $('action').value = '';
  $('failonly').checked = false;
  $('sort').value = 'desc';
  search(true);
};
$('prev').onclick = () => { if (PAGE > 0) { PAGE--; search(false); } };
$('next').onclick = () => { if ((PAGE+1) * parseInt($('pagesize').value,10) < TOTAL) { PAGE++; search(false); } };
$('pagesize').onchange = () => search(true);
$('schema').onchange = () => { const s = $('schema').value; if (s) loadLookups(s); };
$('entity').addEventListener('change', () => { const s = $('schema').value; if (s) loadActions(s, $('entity').value.trim()); });
document.querySelectorAll('.bar input').forEach(inp => inp.addEventListener('keydown', e => { if (e.key === 'Enter') search(true); }));
</script>
</body>
</html>
"""


def _connect(schema: str):
    cfg = get_db_config(schema)
    conn = mysql.connector.connect(
        host=cfg["host"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        connection_timeout=15,
    )
    return conn, cfg


def _build_where(args):
    clauses = []
    params = []

    entity = args.get("entity", "").strip()
    if entity:
        clauses.append("al.entity LIKE %s")
        params.append(f"%{entity}%")

    action = args.get("action", "").strip()
    if action:
        clauses.append("al.action LIKE %s")
        params.append(f"%{action}%")

    ukid = args.get("ukid", "").strip()
    if ukid:
        clauses.append("al.ukid = %s")
        params.append(ukid)

    epk = args.get("epk", "").strip()
    if epk:
        clauses.append("al.entity_primary_key = %s")
        params.append(epk)

    logid = args.get("logid", "").strip()
    if logid:
        clauses.append("al.id = %s")
        params.append(logid)

    date_from = args.get("from", "").strip()
    if date_from:
        clauses.append("al.timestamp >= %s")
        params.append(f"{date_from} 00:00:00")

    date_to = args.get("to", "").strip()
    if date_to:
        clauses.append("al.timestamp <= %s")
        params.append(f"{date_to} 23:59:59")

    keyword = args.get("keyword", "").strip()
    if keyword:
        kw = f"%{keyword}%"
        clauses.append(
            "(al.previous_value LIKE %s OR al.current_value LIKE %s "
            "OR als.previous_value LIKE %s OR als.current_value LIKE %s)"
        )
        params.extend([kw, kw, kw, kw])

    if args.get("failonly", "").strip():
        clauses.append(
            "(al.current_value LIKE %s OR als.current_value LIKE %s "
            "OR al.current_value LIKE %s OR als.current_value LIKE %s)"
        )
        params.extend([
            '%"success":false%', '%"success":false%',
            '%"success": false%', '%"success": false%',
        ])

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params


JOIN_SQL = (
    "FROM audit_log al LEFT JOIN audit_log_status als ON al.id = als.audit_log_id"
)


@app.route("/")
def index():
    return render_template_string(PAGE, schemas=list_schemas())


@app.route("/api/search")
def api_search():
    schema = request.args.get("schema", "").strip()
    if not schema:
        return jsonify(error="No schema provided."), 400
    try:
        cfg = get_db_config(schema)
    except KeyError as e:
        return jsonify(error=str(e)), 404

    try:
        page = max(int(request.args.get("page", 0)), 0)
    except ValueError:
        page = 0
    try:
        page_size = int(request.args.get("page_size", DEFAULT_PAGE_SIZE))
    except ValueError:
        page_size = DEFAULT_PAGE_SIZE
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    sort = "ASC" if request.args.get("sort") == "asc" else "DESC"
    where_sql, params = _build_where(request.args)

    conn = None
    try:
        conn, cfg = _connect(schema)
        cur = conn.cursor(dictionary=True)

        cur.execute(f"SELECT COUNT(*) AS n {JOIN_SQL}{where_sql}", params)
        total = cur.fetchone()["n"]

        query = (
            "SELECT al.id, al.entity, al.entity_primary_key, al.action, al.ukid, al.timestamp, "
            "al.previous_value, al.current_value, "
            "als.id AS status_id, als.previous_value AS status_previous_value, "
            "als.current_value AS status_current_value, als.created_timestamp AS status_timestamp "
            f"{JOIN_SQL}{where_sql} ORDER BY al.id {sort} LIMIT %s OFFSET %s"
        )
        cur.execute(query, params + [page_size, page * page_size])
        rows = cur.fetchall()
        cur.close()

        for row in rows:
            for k, v in row.items():
                if v is not None and not isinstance(v, (str, int, float, bool)):
                    row[k] = str(v)

        return jsonify(schema=cfg["database"], rows=rows, total=total, page=page, page_size=page_size)
    except mysql.connector.Error as e:
        return jsonify(error=f"DB error: {e}"), 500
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/api/entities")
def api_entities():
    schema = request.args.get("schema", "").strip()
    if not schema:
        return jsonify(error="No schema provided."), 400
    conn = None
    try:
        conn, cfg = _connect(schema)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT entity FROM audit_log ORDER BY entity")
        entities = [r[0] for r in cur.fetchall()]
        cur.close()
        return jsonify(entities=entities)
    except mysql.connector.Error as e:
        return jsonify(error=f"DB error: {e}"), 500
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/api/actions")
def api_actions():
    schema = request.args.get("schema", "").strip()
    if not schema:
        return jsonify(error="No schema provided."), 400
    entity = request.args.get("entity", "").strip()
    conn = None
    try:
        conn, cfg = _connect(schema)
        cur = conn.cursor()
        if entity:
            cur.execute("SELECT DISTINCT action FROM audit_log WHERE entity = %s ORDER BY action", (entity,))
        else:
            cur.execute("SELECT DISTINCT action FROM audit_log ORDER BY action")
        actions = [r[0] for r in cur.fetchall()]
        cur.close()
        return jsonify(actions=actions)
    except mysql.connector.Error as e:
        return jsonify(error=f"DB error: {e}"), 500
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
