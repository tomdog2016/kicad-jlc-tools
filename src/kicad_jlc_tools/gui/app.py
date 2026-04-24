"""Tkinter GUI for managing JLC/LCSC part numbers in KiCad schematics."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Optional

from ..schematic import Schematic
from ..database import JLCDatabase
from ..matcher import ComponentMatcher
from ..bom import export_jlc_bom, export_full_bom, import_jlc_codes
from ..models import Component, MatchResult, MatchStatus


class ComponentEditDialog:
    """Popup dialog for editing a single component's LCSC code."""

    def __init__(self, parent, component: Component, db: JLCDatabase, on_save):
        self.component = component
        self.db = db
        self.on_save = on_save
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit - {component.ref}")
        self.dialog.geometry("700x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 450) // 2
        self.dialog.geometry(f"700x450+{x}+{y}")

        self._create_widgets()
        self._do_search()

    def _create_widgets(self):
        main = ttk.Frame(self.dialog, padding="10")
        main.grid(row=0, column=0, sticky="nsew")
        self.dialog.columnconfigure(0, weight=1)
        self.dialog.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        # Info
        info = ttk.LabelFrame(main, text="Component", padding="10")
        info.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(info, text="Ref:").grid(row=0, column=0, padx=5)
        ttk.Label(info, text=self.component.ref, font=("Arial", 10, "bold")).grid(row=0, column=1, padx=5)
        ttk.Label(info, text="Value:").grid(row=0, column=2, padx=5)
        ttk.Label(info, text=self.component.value).grid(row=0, column=3, padx=5)
        ttk.Label(info, text="Footprint:").grid(row=1, column=0, padx=5)
        fp = self.component.footprint
        if len(fp) > 40:
            fp = fp[:37] + "..."
        ttk.Label(info, text=fp).grid(row=1, column=1, columnspan=3, sticky="w", padx=5)
        ttk.Label(info, text="LCSC:").grid(row=2, column=0, padx=5)
        self.current_label = ttk.Label(
            info,
            text=self.component.lcsc or "(none)",
            foreground="blue" if self.component.lcsc else "gray",
        )
        self.current_label.grid(row=2, column=1, columnspan=3, sticky="w", padx=5)

        # Search
        search = ttk.LabelFrame(main, text="Search", padding="10")
        search.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(search, text="Keyword:").grid(row=0, column=0, padx=5)
        self.search_entry = ttk.Entry(search, width=30)
        self.search_entry.grid(row=0, column=1, padx=5)
        self.search_entry.insert(0, f"{self.component.value}")
        self.search_entry.bind("<KeyRelease>", lambda e: self.dialog.after(300, self._do_search))
        ttk.Button(search, text="Search", command=self._do_search).grid(row=0, column=2, padx=5)

        # Results
        rf = ttk.LabelFrame(main, text="Results", padding="10")
        rf.grid(row=2, column=0, sticky="nsew")
        rf.columnconfigure(0, weight=1)
        rf.rowconfigure(0, weight=1)

        cols = ("value", "package", "code")
        self.tree = ttk.Treeview(rf, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("value", text="Value")
        self.tree.heading("package", text="Package")
        self.tree.heading("code", text="LCSC Code")
        self.tree.column("value", width=200)
        self.tree.column("package", width=120)
        self.tree.column("code", width=200)
        sb = ttk.Scrollbar(rf, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda e: self._save_and_close())

        # Buttons
        bf = ttk.Frame(main)
        bf.grid(row=3, column=0, pady=(10, 0))
        ttk.Button(bf, text="Select", command=self._save_and_close).grid(row=0, column=0, padx=5)
        ttk.Button(bf, text="Cancel", command=self.dialog.destroy).grid(row=0, column=1, padx=5)
        ttk.Button(bf, text="Clear", command=self._clear).grid(row=0, column=2, padx=5)

        ttk.Label(bf, text="Manual:").grid(row=1, column=0, sticky="e", padx=5, pady=(5, 0))
        self.manual = ttk.Entry(bf, width=20)
        self.manual.grid(row=1, column=1, padx=5, pady=(5, 0), sticky="w")
        if self.component.lcsc:
            self.manual.insert(0, self.component.lcsc)
        ttk.Button(bf, text="Apply", command=self._use_manual).grid(row=1, column=2, padx=5, pady=(5, 0))

    def _do_search(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.db.is_available:
            self.tree.insert("", tk.END, values=("Database unavailable", "", ""))
            return

        keyword = self.search_entry.get().strip().lower()
        results = self.db.search(self.component.value, self.component.footprint, limit=20)
        if keyword:
            results = [r for r in results if keyword in r.part_number.lower() or keyword in r.description.lower()]

        if not results:
            self.tree.insert("", tk.END, values=("No matches found", "", ""))
            return

        value_lower = self.component.value.lower()
        first_item = None
        for r in results:
            label = r.part_number or r.description
            if r.part_number.lower() == value_lower:
                label = f"* {label}"
            iid = self.tree.insert("", tk.END, values=(label, r.package, r.lcsc))
            if first_item is None:
                first_item = iid
        if first_item:
            self.tree.selection_set(first_item)
            self.tree.see(first_item)

    def _save_and_close(self):
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0])["values"]
            if len(vals) >= 3 and vals[2]:
                self.result = vals[2]
                self.on_save(self.component.ref, vals[2])
                self.dialog.destroy()
                return
        messagebox.showwarning("Warning", "Select a component first", parent=self.dialog)

    def _use_manual(self):
        code = self.manual.get().strip()
        if code:
            self.result = code
            self.on_save(self.component.ref, code)
            self.dialog.destroy()
        else:
            messagebox.showwarning("Warning", "Enter an LCSC code", parent=self.dialog)

    def _clear(self):
        self.result = ""
        self.on_save(self.component.ref, "")
        self.dialog.destroy()


class JLCPartManagerApp:
    """Main Tkinter application."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("KiCad JLC Part Manager")
        self.root.geometry("1200x700")

        self.schematic: Optional[Schematic] = None
        self.db = JLCDatabase()
        self.matcher = ComponentMatcher(self.db)
        self.components: list[Component] = []

        self._build_ui()

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Toolbar
        tb = ttk.Frame(self.root, padding="5")
        tb.grid(row=0, column=0, sticky="ew")

        ttk.Button(tb, text="Open Schematic", command=self._on_load).grid(row=0, column=0, padx=3)
        ttk.Button(tb, text="Save", command=self._on_save).grid(row=0, column=1, padx=3)
        ttk.Button(tb, text="Export BOM", command=self._on_export).grid(row=0, column=2, padx=3)
        ttk.Separator(tb, orient=tk.VERTICAL).grid(row=0, column=3, sticky="ns", padx=8)
        ttk.Button(tb, text="Import Codes", command=self._on_import).grid(row=0, column=4, padx=3)
        ttk.Button(tb, text="Auto Match All", command=self._on_batch_match).grid(row=0, column=5, padx=3)
        ttk.Separator(tb, orient=tk.VERTICAL).grid(row=0, column=6, sticky="ns", padx=8)
        ttk.Button(tb, text="Download DB", command=self._on_download_db).grid(row=0, column=7, padx=3)
        self.file_label = ttk.Label(tb, text="No file loaded", foreground="gray")
        self.file_label.grid(row=0, column=8, padx=10, sticky="w")

        # Component table
        tf = ttk.Frame(self.root, padding="5")
        tf.grid(row=1, column=0, sticky="nsew")
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)

        cols = ("ref", "value", "footprint", "lcsc", "status")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("ref", text="Reference")
        self.tree.heading("value", text="Value")
        self.tree.heading("footprint", text="Footprint")
        self.tree.heading("lcsc", text="LCSC Part")
        self.tree.heading("status", text="Status")
        self.tree.column("ref", width=100)
        self.tree.column("value", width=150)
        self.tree.column("footprint", width=280)
        self.tree.column("lcsc", width=120)
        self.tree.column("status", width=80)

        sb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Edit panel
        ef = ttk.Frame(self.root, padding="5")
        ef.grid(row=2, column=0, sticky="ew")

        ttk.Label(ef, text="LCSC:").grid(row=0, column=0, padx=5)
        self.lcsc_entry = ttk.Entry(ef, width=30)
        self.lcsc_entry.grid(row=0, column=1, padx=5)
        ttk.Button(ef, text="Apply", command=self._apply_lcsc).grid(row=0, column=2, padx=3)
        ttk.Button(ef, text="Clear", command=self._clear_lcsc).grid(row=0, column=3, padx=3)

        ttk.Label(ef, text="Footprint:").grid(row=1, column=0, padx=5, pady=(3, 0))
        self.fp_entry = ttk.Entry(ef, width=30)
        self.fp_entry.grid(row=1, column=1, padx=5, pady=(3, 0))
        ttk.Button(ef, text="Apply FP", command=self._apply_footprint).grid(row=1, column=2, padx=3, pady=(3, 0))
        ttk.Button(ef, text="Restore", command=self._restore_footprint).grid(row=1, column=3, padx=3, pady=(3, 0))

        # Status bar
        self.status = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN)
        self.status.grid(row=3, column=0, sticky="ew", pady=(3, 0))

    def _refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for c in self.components:
            status = c.status.value
            self.tree.insert("", tk.END, values=(
                c.ref, c.value, c.footprint, c.lcsc, status
            ))

    def _selected_component(self) -> Optional[Component]:
        sel = self.tree.selection()
        if not sel:
            return None
        ref = self.tree.item(sel[0])["values"][0]
        for c in self.components:
            if c.ref == ref:
                return c
        return None

    def _on_load(self):
        path = filedialog.askopenfilename(
            title="Open KiCad Schematic",
            filetypes=[("KiCad Schematic", "*.kicad_sch"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            self.schematic = Schematic(path)
            self.components = self.schematic.components
            self.file_label.config(text=Path(path).name)
            self._refresh()
            self.status.config(text=f"Loaded {len(self.components)} components")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    def _on_save(self):
        if not self.schematic:
            return
        try:
            self.schematic.save()
            self.status.config(text=f"Saved to {self.schematic.path.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _on_export(self):
        if not self.components:
            messagebox.showwarning("Warning", "No components to export")
            return
        path = filedialog.asksaveasfilename(
            title="Export BOM", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        export_jlc_bom(self.components, path)
        self.status.config(text=f"Exported to {Path(path).name}")

    def _on_import(self):
        if not self.components:
            messagebox.showwarning("Warning", "Load a schematic first")
            return
        path = filedialog.askopenfilename(
            title="Import LCSC Codes",
            filetypes=[("CSV", "*.csv"), ("JSON", "*.json")],
        )
        if not path:
            return
        count, warnings = import_jlc_codes(self.components, path)
        self._refresh()
        msg = f"Updated {count} components"
        if warnings:
            msg += f" ({len(warnings)} warnings)"
        self.status.config(text=msg)

    def _on_batch_match(self):
        if not self.components:
            messagebox.showwarning("Warning", "Load a schematic first")
            return
        if not self.db.is_available:
            messagebox.showwarning("Warning", "Database not found. Download it first.")
            return

        unmatched = [c for c in self.components if not c.lcsc]
        if not unmatched:
            messagebox.showinfo("Info", "All components already have LCSC codes")
            return

        if not messagebox.askyesno("Confirm", f"Auto-match {len(unmatched)} components?"):
            return

        self.status.config(text="Matching...")

        def worker():
            self.matcher.match_all(self.components)

            def done():
                self._refresh()
                matched = sum(1 for c in self.components if c.lcsc)
                self.status.config(text=f"Matched {matched}/{len(self.components)}")

            self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_db(self):
        self.status.config(text="Downloading database...")

        def worker():
            try:
                JLCDatabase.download()

                def done():
                    self.db = JLCDatabase()
                    self.matcher = ComponentMatcher(self.db)
                    self.status.config(text=f"Database ready ({self.db.db_size_mb:.0f} MB)")

                self.root.after(0, done)
            except Exception as e:

                def fail():
                    self.status.config(text=f"Download failed: {e}")

                self.root.after(0, fail)

        threading.Thread(target=worker, daemon=True).start()

    def _on_double_click(self, event):
        comp = self._selected_component()
        if not comp:
            return
        ComponentEditDialog(self.root, comp, self.db, self._on_component_edited)
        self.lcsc_entry.delete(0, tk.END)
        self.lcsc_entry.insert(0, comp.lcsc)
        self.fp_entry.delete(0, tk.END)
        self.fp_entry.insert(0, comp.footprint)

    def _on_select(self, event):
        comp = self._selected_component()
        if not comp:
            return
        self.lcsc_entry.delete(0, tk.END)
        self.lcsc_entry.insert(0, comp.lcsc)
        self.fp_entry.delete(0, tk.END)
        self.fp_entry.insert(0, comp.footprint)

    def _on_component_edited(self, ref: str, lcsc_code: str):
        for c in self.components:
            if c.ref == ref:
                c.lcsc = lcsc_code
                c.status = MatchStatus.MANUAL if lcsc_code else MatchStatus.PENDING
                break
        if self.schematic and lcsc_code:
            self.schematic.set_lcsc(ref, lcsc_code)
        self._refresh()
        self.status.config(text=f"Updated {ref}: {lcsc_code or '(cleared)'}")

    def _apply_lcsc(self):
        comp = self._selected_component()
        if not comp:
            return
        code = self.lcsc_entry.get().strip()
        if code:
            comp.lcsc = code
            comp.status = MatchStatus.MANUAL
            if self.schematic:
                self.schematic.set_lcsc(comp.ref, code)
            self._refresh()
            self.status.config(text=f"Set {comp.ref} LCSC={code}")

    def _clear_lcsc(self):
        comp = self._selected_component()
        if not comp:
            return
        comp.lcsc = ""
        comp.status = MatchStatus.PENDING
        self.lcsc_entry.delete(0, tk.END)
        if self.schematic:
            self.schematic.set_lcsc(comp.ref, "")
        self._refresh()

    def _apply_footprint(self):
        comp = self._selected_component()
        if not comp:
            return
        new_fp = self.fp_entry.get().strip()
        if not new_fp:
            return
        comp.footprint = new_fp
        if self.schematic:
            self.schematic.set_footprint(comp.ref, new_fp)
        self._refresh()
        self.status.config(text=f"Set {comp.ref} footprint (saved on Save)")

    def _restore_footprint(self):
        comp = self._selected_component()
        if not comp:
            return
        original = comp.footprint_full
        comp.footprint = original
        self.fp_entry.delete(0, tk.END)
        self.fp_entry.insert(0, original)
        self._refresh()
        self.status.config(text=f"Restored {comp.ref} footprint")


def main():
    root = tk.Tk()
    JLCPartManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
