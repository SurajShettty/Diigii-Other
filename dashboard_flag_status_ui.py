"""Dashboard / Feature Flag status checker.

For a tenant, shows every embedded dashboard (analytics_tenant_module_report,
central config DB) alongside whether the feature flag(s) that dashboard
actually depends on are open for that tenant (college_feature_flag/feature,
per-tenant DB). The dashboard -> feature_flags link is traced through
pipelines.json (dag_id -> output tables -> feature_flags) and the Zoho
Analytics /dependents API (table view -> dependent dashboard view), cached in
dashboard_view_flag_map.json. Use "Rebuild dag->flag mapping" to (re)build
that cache - it hits the Zoho API and is slow; the tenant-status lookups
below it are cheap DB reads and use whatever is currently cached.

Run:
    python dashboard_flag_status_ui.py
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import pandas as pd

import dashboard_flag_core as core
from db_env import list_schemas

DEFAULT_FORMAT = "Excel (.xlsx)"
FORMAT_OPTIONS = [DEFAULT_FORMAT, "CSV (.csv)"]

COLUMNS = [
    "module", "report_name", "embedded", "source_tables", "required_flags",
    "flags_detail", "pipelines_scheduled", "status", "tenant_id", "workspace_id", "view_id",
]
COLUMN_LABELS = {
    "module": "Module", "report_name": "Report Name", "embedded": "Embedded",
    "source_tables": "Source Table(s)", "required_flags": "Required Flags",
    "flags_detail": "Flag Status", "pipelines_scheduled": "Pipelines Scheduled",
    "status": "Overall Status", "tenant_id": "Tenant ID",
    "workspace_id": "Workspace ID", "view_id": "View ID",
}


class DashboardFlagUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Dashboard / Feature Flag Status")
        self.root.geometry("1150x750")
        self.root.minsize(850, 550)

        self._embed_df: pd.DataFrame | None = None
        self._dashboard_map: dict = {}
        self._last_df: pd.DataFrame | None = None

        self._build_widgets()
        self._set_default_output()
        self._load_dashboard_map(silent=True)

    # ---- UI construction ---------------------------------------------------

    def _build_widgets(self):
        pad = {"padx": 12, "pady": 8}

        top_frame = ttk.LabelFrame(self.root, text="Tenant / Cache")
        top_frame.pack(fill="x", **pad)

        ttk.Label(top_frame, text="Tenant schema:").pack(side="left", padx=(0, 4))
        self.schema_var = tk.StringVar()
        self.schema_combo = ttk.Combobox(
            top_frame, textvariable=self.schema_var, values=list_schemas(), width=40,
        )
        self.schema_combo.pack(side="left", padx=(0, 8))
        if self.schema_combo["values"]:
            self.schema_combo.current(0)

        self.load_btn = ttk.Button(top_frame, text="Load status", command=self._on_load_tenant)
        self.load_btn.pack(side="left", padx=(0, 8))

        self.refresh_embed_btn = ttk.Button(
            top_frame, text="Refresh dashboard cache", command=self._on_refresh_embed_cache,
        )
        self.refresh_embed_btn.pack(side="left", padx=(0, 8))

        self.all_tenants_btn = ttk.Button(
            top_frame, text="Export ALL tenants...", command=self._on_export_all_tenants,
        )
        self.all_tenants_btn.pack(side="left", padx=(0, 8))

        self.cache_status_var = tk.StringVar(value="Dashboard cache: not loaded")
        ttk.Label(top_frame, textvariable=self.cache_status_var).pack(side="right")

        map_frame = ttk.Frame(self.root)
        map_frame.pack(fill="x", padx=12)

        self.rebuild_map_btn = ttk.Button(
            map_frame, text="Rebuild dag->flag mapping (Zoho API, slow)", command=self._on_rebuild_dashboard_map,
        )
        self.rebuild_map_btn.pack(side="left", padx=(0, 8), pady=(0, 4))

        self.map_status_var = tk.StringVar(value=self._dashboard_map_status_text())
        ttk.Label(map_frame, textvariable=self.map_status_var).pack(side="left")

        # ---- Filter ------------------------------------------------------
        filter_frame = ttk.Frame(self.root)
        filter_frame.pack(fill="x", padx=12)
        ttk.Label(filter_frame, text="Filter (module / report name / status):").pack(side="left", padx=(0, 4))
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())
        ttk.Entry(filter_frame, textvariable=self.filter_var, width=50).pack(side="left")

        # ---- Results table -------------------------------------------------
        table_frame = ttk.LabelFrame(self.root, text="Dashboard status for selected tenant")
        table_frame.pack(fill="both", expand=True, **pad)

        tree_container = ttk.Frame(table_frame)
        tree_container.pack(fill="both", expand=True, padx=4, pady=4)

        self.tree = ttk.Treeview(tree_container, columns=COLUMNS, show="headings")
        for col in COLUMNS:
            self.tree.heading(col, text=COLUMN_LABELS[col])
            width = 220 if col in ("report_name", "required_flags", "flags_detail", "pipelines_scheduled") else 110
            self.tree.column(col, width=width, anchor="w")

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # ---- Export (current tenant) ---------------------------------------
        export_frame = ttk.LabelFrame(self.root, text="Export current view")
        export_frame.pack(fill="x", **pad)

        ttk.Label(export_frame, text="Format:").pack(side="left", padx=(0, 4))
        self.format_var = tk.StringVar(value=DEFAULT_FORMAT)
        ttk.Combobox(
            export_frame, textvariable=self.format_var, values=FORMAT_OPTIONS,
            state="readonly", width=16,
        ).pack(side="left", padx=(0, 12))

        self.output_var = tk.StringVar()
        ttk.Entry(export_frame, textvariable=self.output_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(export_frame, text="Browse", command=self._browse_output).pack(side="right", padx=(4, 0))
        self.export_btn = ttk.Button(export_frame, text="Export", command=self._on_export_current, state="disabled")
        self.export_btn.pack(side="right", padx=(4, 0))

        # ---- Log -------------------------------------------------------------
        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", **pad)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap="word", state="disabled", height=7)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ---- helpers -------------------------------------------------------------

    def _log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{datetime.now():%H:%M:%S}  {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_default_output(self):
        desktop = os.path.join(str(Path.home()), "Desktop")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_var.set(os.path.join(desktop, f"dashboard_flag_status_{timestamp}.xlsx"))

    def _browse_output(self):
        fmt = self.format_var.get()
        if fmt == "CSV (.csv)":
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        else:
            path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if path:
            self.output_var.set(path)

    def _dashboard_map_status_text(self) -> str:
        n_ws = len(self._dashboard_map)
        n_dash = sum(len(v) for v in self._dashboard_map.values())
        if n_ws == 0:
            return "dag->flag mapping: not built yet (click Rebuild)"
        return f"dag->flag mapping: {n_dash} dashboard(s) across {n_ws} workspace(s) (from {core.DASHBOARD_MAP_CACHE_PATH.name})"

    def _load_dashboard_map(self, silent: bool = False):
        try:
            self._dashboard_map = core.load_dashboard_view_flag_map()
            if hasattr(self, "map_status_var"):
                self.map_status_var.set(self._dashboard_map_status_text())
            if not silent:
                self._log(self._dashboard_map_status_text())
        except Exception as exc:
            messagebox.showerror("Dashboard map error", str(exc))

    def _load_preview(self, df: pd.DataFrame):
        self.tree.delete(*self.tree.get_children())
        for _, row in df.iterrows():
            values = [row.get(c, "") for c in COLUMNS]
            self.tree.insert("", "end", values=values)

    def _apply_filter(self):
        if self._last_df is None:
            return
        term = self.filter_var.get().strip().lower()
        if not term:
            self._load_preview(self._last_df)
            return
        mask = self._last_df.apply(
            lambda r: term in str(r.get("module", "")).lower()
            or term in str(r.get("report_name", "")).lower()
            or term in str(r.get("status", "")).lower(),
            axis=1,
        )
        self._load_preview(self._last_df[mask])

    # ---- actions ---------------------------------------------------------

    def _on_refresh_embed_cache(self):
        self.refresh_embed_btn.configure(state="disabled")
        self.cache_status_var.set("Dashboard cache: loading...")
        self._log("Fetching embedded-dashboard data from configurations DB...")

        def run():
            try:
                df = core.fetch_embedded_dashboards()
                self.root.after(0, self._on_embed_loaded, df)
            except Exception as exc:
                self.root.after(0, self._on_error, exc)
            finally:
                self.root.after(0, lambda: self.refresh_embed_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _on_embed_loaded(self, df: pd.DataFrame):
        self._embed_df = df
        self.cache_status_var.set(f"Dashboard cache: {len(df)} row(s) loaded")
        self._log(f"Dashboard cache loaded: {len(df)} embedded dashboard rows.")

    def _on_load_tenant(self):
        schema = self.schema_var.get().strip()
        if not schema:
            messagebox.showerror("Missing schema", "Please select a tenant schema.")
            return
        if self._embed_df is None:
            messagebox.showinfo("Loading cache first", "Dashboard cache isn't loaded yet - fetching it now.")
            self._on_refresh_embed_cache_then(lambda: self._load_tenant(schema))
            return
        self._load_tenant(schema)

    def _on_refresh_embed_cache_then(self, callback):
        self.refresh_embed_btn.configure(state="disabled")
        self.cache_status_var.set("Dashboard cache: loading...")

        def run():
            try:
                df = core.fetch_embedded_dashboards()
                self.root.after(0, self._on_embed_loaded, df)
                self.root.after(0, callback)
            except Exception as exc:
                self.root.after(0, self._on_error, exc)
            finally:
                self.root.after(0, lambda: self.refresh_embed_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _on_rebuild_dashboard_map(self):
        if self._embed_df is None:
            messagebox.showinfo(
                "Loading cache first",
                "Dashboard cache isn't loaded yet - fetching it now, then rebuilding the mapping.",
            )
            self._on_refresh_embed_cache_then(self._rebuild_dashboard_map)
            return
        self._rebuild_dashboard_map()

    def _rebuild_dashboard_map(self):
        workspace_ids = sorted(self._embed_df["workspace_id"].astype(str).unique())
        if not messagebox.askyesno(
            "Rebuild dag->flag mapping",
            f"This calls the Zoho Analytics API across {len(workspace_ids)} workspace(s) and can take "
            f"several minutes. Continue?",
        ):
            return

        self.rebuild_map_btn.configure(state="disabled")
        self.map_status_var.set("dag->flag mapping: rebuilding...")
        self._log(f"Rebuilding dag->flag mapping for {len(workspace_ids)} workspace(s)...")

        def log_cb(msg):
            self.root.after(0, self._log, msg)

        def run():
            try:
                mapping = core.rebuild_dashboard_view_flag_map(workspace_ids, log_cb=log_cb)
                self.root.after(0, self._on_dashboard_map_rebuilt, mapping)
            except Exception as exc:
                self.root.after(0, self._on_error, exc)
            finally:
                self.root.after(0, lambda: self.rebuild_map_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _on_dashboard_map_rebuilt(self, mapping: dict):
        self._dashboard_map = mapping
        self.map_status_var.set(self._dashboard_map_status_text())
        self._log("dag->flag mapping rebuilt. " + self._dashboard_map_status_text())

    def _load_tenant(self, schema: str):
        self._load_dashboard_map(silent=True)
        self.load_btn.configure(state="disabled")
        self.export_btn.configure(state="disabled")
        self._log(f"Looking up {schema}: college_id, feature flags, dashboard status...")

        def run():
            try:
                df = core.build_tenant_dashboard_report(schema, self._embed_df, self._dashboard_map)
                self.root.after(0, self._on_tenant_loaded, schema, df)
            except Exception as exc:
                self.root.after(0, self._on_error, exc)

        threading.Thread(target=run, daemon=True).start()

    def _on_tenant_loaded(self, schema: str, df: pd.DataFrame):
        self._last_df = df
        self.filter_var.set("")
        self._load_preview(df)
        self.load_btn.configure(state="normal")
        self.export_btn.configure(state="normal" if not df.empty else "disabled")
        if df.empty:
            self._log(f"{schema}: no embedded dashboards found for this tenant (or tenant_id/college_id mismatch).")
        else:
            not_ready = (df["status"] != core.READY).sum()
            self._log(f"{schema}: {len(df)} dashboard(s), {not_ready} not fully ready.")

    def _on_error(self, exc: Exception):
        self.load_btn.configure(state="normal")
        self.refresh_embed_btn.configure(state="normal")
        self._log(f"ERROR: {exc}")
        messagebox.showerror("Error", str(exc))

    def _on_export_current(self):
        if self._last_df is None or self._last_df.empty:
            messagebox.showerror("Nothing to export", "Load a tenant's status first.")
            return
        output_path = self.output_var.get().strip()
        if not output_path:
            messagebox.showerror("Missing output", "Please specify an export path.")
            return
        try:
            if output_path.lower().endswith(".csv"):
                self._last_df.to_csv(output_path, index=False)
            else:
                self._last_df.to_excel(output_path, index=False)
            self._log(f"Exported {len(self._last_df)} row(s) to {output_path}")
            messagebox.showinfo("Export complete", f"Saved to {output_path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _on_export_all_tenants(self):
        if self._embed_df is None:
            messagebox.showinfo("Loading cache first", "Dashboard cache isn't loaded yet - fetching it now.")
            self._on_refresh_embed_cache_then(self._export_all_tenants)
            return
        self._export_all_tenants()

    def _export_all_tenants(self):
        output_path = filedialog.asksaveasfilename(
            title="Save all-tenant report",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not output_path:
            return

        self._load_dashboard_map(silent=True)
        schemas = list_schemas()
        self.all_tenants_btn.configure(state="disabled")
        self._log(f"Building report for all {len(schemas)} tenant(s) - this can take a while...")

        def progress(i, total, schema):
            self.root.after(0, self._log, f"[{i}/{total}] {schema}")

        def run():
            try:
                combined, errors = core.build_all_tenants_report(
                    schemas, self._embed_df, self._dashboard_map, progress_cb=progress,
                )
                self.root.after(0, self._on_all_tenants_done, combined, errors, output_path)
            except Exception as exc:
                self.root.after(0, self._on_error, exc)
            finally:
                self.root.after(0, lambda: self.all_tenants_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _on_all_tenants_done(self, combined: pd.DataFrame, errors: list, output_path: str):
        if combined.empty:
            self._log("No data collected across any tenant.")
        else:
            summary = combined["status"].value_counts().reset_index()
            summary.columns = ["status", "count"]
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                combined.to_excel(writer, sheet_name="Full_Detail", index=False)
                summary.to_excel(writer, sheet_name="Summary", index=False)
                if errors:
                    pd.DataFrame(errors, columns=["schema", "error"]).astype(str).to_excel(
                        writer, sheet_name="Errors", index=False,
                    )
            self._log(f"All-tenant report written to {output_path} ({len(combined)} rows, {len(errors)} tenant error(s)).")
            messagebox.showinfo("Export complete", f"Saved to {output_path}\n{len(errors)} tenant(s) failed - see Errors sheet.")
        if errors:
            for schema, exc in errors:
                self._log(f"  skipped {schema}: {exc}")


def main():
    root = tk.Tk()
    DashboardFlagUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
