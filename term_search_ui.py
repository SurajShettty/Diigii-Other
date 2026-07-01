"""Small web UI to browse the `term` table of any tenant schema.

Enter a schema name (full "collpoll_sgbs" or short "sgbs"), it runs
`SELECT * FROM term` against that tenant's read replica (credentials from
db_credentials.json via db_env.get_db_config) and shows every row. A keyword
box filters the loaded rows instantly across all columns.

Run:
    python term_search_ui.py
Then open http://127.0.0.1:5000 in a browser.
"""

import mysql.connector
from flask import Flask, jsonify, render_template_string, request

from db_env import get_db_config, list_schemas

app = Flask(__name__)

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Term Search</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 0; background: #f5f6f8; color: #1c1e21; }
    header { background: #1f2937; color: #fff; padding: 16px 24px; }
    header h1 { margin: 0; font-size: 18px; font-weight: 600; }
    .bar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; padding: 16px 24px; background: #fff; border-bottom: 1px solid #e2e5e9; }
    input, button { font-size: 14px; padding: 8px 12px; border: 1px solid #cfd4da; border-radius: 6px; }
    input { min-width: 220px; }
    button { background: #2563eb; color: #fff; border-color: #2563eb; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    #status { padding: 8px 24px; font-size: 13px; color: #555; }
    #status.err { color: #b91c1c; }
    .wrap { padding: 0 24px 40px; overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; background: #fff; font-size: 13px; }
    th, td { border: 1px solid #e2e5e9; padding: 6px 10px; text-align: left; white-space: nowrap; }
    th { background: #f0f2f5; position: sticky; top: 0; cursor: pointer; }
    th:hover { background: #e4e7ec; }
    tr:nth-child(even) td { background: #fafbfc; }
    mark { background: #fde68a; padding: 0; }
  </style>
</head>
<body>
  <header><h1>Term Search &mdash; select * from term</h1></header>
  <div class="bar">
    <input id="schema" list="schemas" placeholder="Schema e.g. collpoll_sgbs or sgbs" autofocus>
    <datalist id="schemas">
      {% for s in schemas %}<option value="{{ s }}">{% endfor %}
    </datalist>
    <button id="load">Load terms</button>
    <input id="filter" placeholder="Filter loaded rows by keyword…" disabled>
    <span id="count"></span>
  </div>
  <div id="status">Enter a schema name and click Load terms.</div>
  <div class="wrap"><table id="tbl"><thead></thead><tbody></tbody></table></div>

<script>
let COLS = [], ROWS = [], sortCol = null, sortAsc = true;
const $ = id => document.getElementById(id);

async function load() {
  const schema = $('schema').value.trim();
  if (!schema) { setStatus('Please enter a schema name.', true); return; }
  setStatus('Loading ' + schema + ' …');
  $('load').disabled = true;
  try {
    const r = await fetch('/terms?schema=' + encodeURIComponent(schema));
    const data = await r.json();
    if (!r.ok) { setStatus(data.error || 'Request failed.', true); clear(); return; }
    COLS = data.columns; ROWS = data.rows;
    $('filter').disabled = false; $('filter').value = '';
    sortCol = null;
    render();
    setStatus('Loaded ' + ROWS.length + ' term(s) from ' + data.schema + '.');
  } catch (e) {
    setStatus('Error: ' + e, true); clear();
  } finally {
    $('load').disabled = false;
  }
}

function currentRows() {
  const q = $('filter').value.trim().toLowerCase();
  let rows = ROWS;
  if (q) {
    const terms = q.split(/\s+/);
    rows = ROWS.filter(row =>
      terms.every(t => COLS.some(c => String(row[c] ?? '').toLowerCase().includes(t)))
    );
  }
  if (sortCol !== null) {
    rows = rows.slice().sort((a, b) => {
      let x = a[sortCol], y = b[sortCol];
      const nx = parseFloat(x), ny = parseFloat(y);
      if (!isNaN(nx) && !isNaN(ny)) { x = nx; y = ny; }
      else { x = String(x ?? '').toLowerCase(); y = String(y ?? '').toLowerCase(); }
      if (x < y) return sortAsc ? -1 : 1;
      if (x > y) return sortAsc ? 1 : -1;
      return 0;
    });
  }
  return rows;
}

function render() {
  const rows = currentRows();
  const q = $('filter').value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const thead = $('tbl').tHead, tbody = $('tbl').tBodies[0];
  thead.innerHTML = '<tr>' + COLS.map(c =>
    '<th data-c="' + c + '">' + c + (sortCol === c ? (sortAsc ? ' ▲' : ' ▼') : '') + '</th>'
  ).join('') + '</tr>';
  thead.querySelectorAll('th').forEach(th => th.onclick = () => {
    const c = th.dataset.c;
    if (sortCol === c) sortAsc = !sortAsc; else { sortCol = c; sortAsc = true; }
    render();
  });
  tbody.innerHTML = rows.map(row =>
    '<tr>' + COLS.map(c => '<td>' + hl(row[c], q) + '</td>').join('') + '</tr>'
  ).join('');
  $('count').textContent = rows.length + ' / ' + ROWS.length + ' rows';
}

function hl(val, terms) {
  let s = esc(val == null ? '' : String(val));
  for (const t of terms) {
    if (!t) continue;
    s = s.replace(new RegExp('(' + t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi'), '<mark>$1</mark>');
  }
  return s;
}
const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function setStatus(m, err) { const s = $('status'); s.textContent = m; s.className = err ? 'err' : ''; }
function clear() { $('tbl').tHead.innerHTML = ''; $('tbl').tBodies[0].innerHTML = ''; $('count').textContent = ''; }

$('load').onclick = load;
$('schema').addEventListener('keydown', e => { if (e.key === 'Enter') load(); });
$('filter').addEventListener('input', render);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, schemas=list_schemas())


@app.route("/terms")
def terms():
    schema = request.args.get("schema", "").strip()
    if not schema:
        return jsonify(error="No schema provided."), 400
    try:
        cfg = get_db_config(schema)
    except KeyError as e:
        return jsonify(error=str(e)), 404

    conn = None
    try:
        conn = mysql.connector.connect(
            host=cfg["host"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            connection_timeout=15,
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM term")
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
        cur.close()
        # JSON-safe: stringify dates/decimals/bytes that aren't natively serialisable.
        for row in rows:
            for k, v in row.items():
                if v is not None and not isinstance(v, (str, int, float, bool)):
                    row[k] = str(v)
        return jsonify(schema=cfg["database"], columns=columns, rows=rows)
    except mysql.connector.Error as e:
        return jsonify(error=f"DB error: {e}"), 500
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
