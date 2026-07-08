"""Generic query runner UI.

Pick a tenant schema from db_credentials.json, enter any SELECT query, choose an
export path/format, and run. Results are saved to the chosen path and a short
preview is shown in the window.

Run:
    python query_runner_ui.py
"""

from __future__ import annotations

import csv
import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import pandas as pd

# mysql-connector-python may not be installed in every venv; guard the import.
try:
    import mysql.connector
except ImportError as exc:  # pragma: no cover
    mysql = None
    _mysql_import_error = exc
else:
    _mysql_import_error = None

from db_env import get_db_config, list_schemas

DEFAULT_FORMAT = "Excel (.xlsx)"
FORMAT_OPTIONS = [DEFAULT_FORMAT, "CSV (.csv)"]


class QueryRunnerUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Generic Query Runner")
        self.root.geometry("900x750")
        self.root.minsize(700, 550)

        self._build_widgets()
        self._set_default_output()

    def _build_widgets(self):
        pad = {"padx": 12, "pady": 8}

        # ---- Schema selection ------------------------------------------------
        schema_frame = ttk.LabelFrame(self.root, text="Tenant / Schema")
        schema_frame.pack(fill="x", **pad)

        self.schema_var = tk.StringVar()
        self.schema_combo = ttk.Combobox(
            schema_frame,
            textvariable=self.schema_var,
            values=list_schemas(),
            width=50,
        )
        self.schema_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if self.schema_combo["values"]:
            self.schema_combo.current(0)

        ttk.Button(schema_frame, text="Refresh list", command=self._refresh_schemas).pack(side="right")

        # ---- Query input -----------------------------------------------------
        query_frame = ttk.LabelFrame(self.root, text="SQL Query")
        query_frame.pack(fill="both", expand=True, **pad)

        self.query_text = scrolledtext.ScrolledText(
            query_frame,
            wrap="word",
            height=12,
            font=("Consolas", 10),
        )
        self.query_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.query_text.insert("1.0", "SELECT * FROM term LIMIT 100;")

        # ---- Export options --------------------------------------------------
        export_frame = ttk.LabelFrame(self.root, text="Export")
        export_frame.pack(fill="x", **pad)

        ttk.Label(export_frame, text="Format:").pack(side="left", padx=(0, 4))
        self.format_var = tk.StringVar(value=DEFAULT_FORMAT)
        ttk.Combobox(
            export_frame,
            textvariable=self.format_var,
            values=FORMAT_OPTIONS,
            state="readonly",
            width=16,
        ).pack(side="left", padx=(0, 12))

        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(export_frame, textvariable=self.output_var)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Button(export_frame, text="Browse", command=self._browse_output).pack(side="right", padx=(4, 0))
        ttk.Button(export_frame, text="Reset", command=self._set_default_output).pack(side="right", padx=(4, 0))

        # ---- Run button ------------------------------------------------------
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=12, pady=(4, 0))

        self.run_btn = ttk.Button(
            btn_frame,
            text="Run Query & Export",
            command=self._on_run,
        )
        self.run_btn.pack(side="left")

        # ---- Preview ---------------------------------------------------------
        preview_frame = ttk.LabelFrame(self.root, text="Preview (first 100 rows)")
        preview_frame.pack(fill="both", expand=True, **pad)

        # Treeview with scrollbars
        tree_container = ttk.Frame(preview_frame)
        tree_container.pack(fill="both", expand=True, padx=4, pady=4)

        self.tree = ttk.Treeview(tree_container, show="headings")
        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # ---- Log area --------------------------------------------------------
        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="x", **pad)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap="word",
            state="disabled",
            height=6,
        )
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{datetime.now():%H:%M:%S}  {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_default_output(self):
        desktop = os.path.join(str(Path.home()), "Desktop")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = os.path.join(desktop, f"query_result_{timestamp}.xlsx")
        self.output_var.set(default)

    def _browse_output(self):
        fmt = self.format_var.get()
        if fmt == "CSV (.csv)":
            path = filedialog.asksaveasfilename(
                title="Save query result as CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
        else:
            path = filedialog.asksaveasfilename(
                title="Save query result as Excel",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            )
        if path:
            self.output_var.set(path)

    def _refresh_schemas(self):
        self.schema_combo["values"] = list_schemas()
        self._log("Schema list refreshed.")

    def _on_run(self):
        if _mysql_import_error:
            messagebox.showerror(
                "Missing dependency",
                f"mysql-connector-python is required.\n{_mysql_import_error}",
            )
            return

        schema = self.schema_var.get().strip()
        query = self.query_text.get("1.0", "end").strip()
        output_path = self.output_var.get().strip()
        fmt = self.format_var.get()

        if not schema:
            messagebox.showerror("Missing schema", "Please select a tenant schema.")
            return
        if not query:
            messagebox.showerror("Missing query", "Please enter a SQL query.")
            return
        if not output_path:
            messagebox.showerror("Missing output", "Please specify an export path.")
            return

        # Normalize extension based on selected format
        base, ext = os.path.splitext(output_path)
        if fmt == "CSV (.csv)":
            if ext.lower() != ".csv":
                output_path = base + ".csv"
                self.output_var.set(output_path)
        else:
            if ext.lower() != ".xlsx":
                output_path = base + ".xlsx"
                self.output_var.set(output_path)

        self._clear_log()
        self.run_btn.configure(state="disabled")
        self._log("Connecting to database...")

        def run():
            try:
                cfg = get_db_config(schema)
                self.root.after(0, self._log, f"Using schema: {cfg['database']}")

                conn = mysql.connector.connect(
                    host=cfg["host"],
                    user=cfg["user"],
                    password=cfg["password"],
                    database=cfg["database"],
                    connection_timeout=60,
                )
                try:
                    self.root.after(0, self._log, "Running query...")
                    df = pd.read_sql(query, conn)
                    self.root.after(0, self._log, f"Fetched {len(df)} row(s), {len(df.columns)} column(s).")

                    self.root.after(0, self._log, f"Exporting to {output_path} ...")
                    if fmt == "CSV (.csv)":
                        df.to_csv(output_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
                    else:
                        df.to_excel(output_path, index=False, engine="openpyxl")
                    self.root.after(0, self._log, "Export complete.")

                    self.root.after(0, self._load_preview, df)
                    self.root.after(0, self._on_success, output_path, len(df))
                finally:
                    conn.close()
            except Exception as exc:
                self.root.after(0, self._on_error, exc)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _load_preview(self, df: pd.DataFrame):
        # Clear previous preview
        self.tree.delete(*self.tree.get_children())
        for col in self.tree["columns"]:
            self.tree.heading(col, text="")
        self.tree["columns"] = ()

        preview_df = df.head(100)
        cols = [str(c) for c in preview_df.columns]
        self.tree["columns"] = cols
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="w")

        for _, row in preview_df.iterrows():
            values = [self._format_cell(v) for v in row.values]
            self.tree.insert("", "end", values=values)

    @staticmethod
    def _format_cell(value) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, (bytes, bytearray)):
            return str(value)
        return str(value)

    def _on_success(self, output_path: str, row_count: int):
        self.run_btn.configure(state="normal")
        messagebox.showinfo(
            "Export Complete",
            f"Saved {row_count} row(s) to:\n{output_path}",
        )

    def _on_error(self, exc: Exception):
        self.run_btn.configure(state="normal")
        msg = f"ERROR: {exc}"
        self._log(msg)
        messagebox.showerror("Query Failed", str(exc))


def main():
    root = tk.Tk()
    app = QueryRunnerUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
