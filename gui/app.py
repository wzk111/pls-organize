from __future__ import annotations
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from engine.scanner import scan_folder
from engine.rules import load_rules_yaml
from engine.planner import build_plan
from engine.executor import apply_plan, undo_last
from engine.llm.generator import generate_rules_yaml


def _write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("pls-organize")
        self.geometry("980x640")

        self.root_dir = tk.StringVar(value="")
        self.rules_path = tk.StringVar(value="rules.generated.yaml")
        self.journal_dir = tk.StringVar(value=".pls-organize-journal")
        self.min_conf = tk.DoubleVar(value=0.0)
        self.conflict_strategy = tk.StringVar(value="rename")

        self.plan = None  # dict payload
        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.root_dir, width=70).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse", command=self.on_browse).grid(row=0, column=2)

        ttk.Label(top, text="Rules file:").grid(row=1, column=0, sticky="w", pady=(8,0))
        ttk.Entry(top, textvariable=self.rules_path, width=70).grid(row=1, column=1, sticky="we", padx=6, pady=(8,0))
        ttk.Button(top, text="Load rules", command=self.on_load_rules).grid(row=1, column=2, pady=(8,0))

        # AI input
        ttk.Label(top, text="Natural language (optional):").grid(row=2, column=0, sticky="nw", pady=(10,0))
        self.nl = tk.Text(top, height=4, width=70)
        self.nl.grid(row=2, column=1, sticky="we", padx=6, pady=(10,0))
        ttk.Button(top, text="Generate rules", command=self.on_generate_rules).grid(row=2, column=2, pady=(10,0))

        opts = ttk.Frame(self, padding=10)
        opts.pack(fill="x")

        ttk.Label(opts, text="Conflict:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(opts, textvariable=self.conflict_strategy, values=["rename", "skip", "overwrite"], width=12).grid(row=0, column=1, padx=6)

        ttk.Label(opts, text="Min confidence:").grid(row=0, column=2, sticky="w")
        ttk.Entry(opts, textvariable=self.min_conf, width=8).grid(row=0, column=3, padx=6)

        ttk.Label(opts, text="Journal dir:").grid(row=0, column=4, sticky="w")
        ttk.Entry(opts, textvariable=self.journal_dir, width=25).grid(row=0, column=5, padx=6)

        btns = ttk.Frame(self, padding=10)
        btns.pack(fill="x")
        ttk.Button(btns, text="Scan", command=self.on_scan).pack(side="left")
        ttk.Button(btns, text="Plan (Preview)", command=self.on_plan).pack(side="left", padx=8)
        ttk.Button(btns, text="Apply", command=self.on_apply).pack(side="left", padx=8)
        ttk.Button(btns, text="Undo last", command=self.on_undo).pack(side="left", padx=8)

        # Plan preview table
        mid = ttk.Frame(self, padding=10)
        mid.pack(fill="both", expand=True)

        cols = ("confidence", "from", "to", "reason")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings")
        self.tree.heading("confidence", text="Confidence")
        self.tree.heading("from", text="From")
        self.tree.heading("to", text="To")
        self.tree.heading("reason", text="Reason")
        self.tree.column("confidence", width=90, anchor="center")
        self.tree.column("from", width=330)
        self.tree.column("to", width=330)
        self.tree.column("reason", width=200)
        self.tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scroll.set)
        scroll.pack(side="right", fill="y")

        # status
        self.status = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self.status, padding=10).pack(fill="x")

        top.columnconfigure(1, weight=1)

    def on_browse(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.root_dir.set(path)

    def on_generate_rules(self) -> None:
        text = self.nl.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("pls-organize", "Please input a natural language instruction first.")
            return
        yaml_str = generate_rules_yaml(text)
        _write_text(self.rules_path.get(), yaml_str)
        messagebox.showinfo("pls-organize", f"Generated rules saved to: {self.rules_path.get()}")

    def on_load_rules(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("YAML", "*.yaml *.yml"), ("All", "*.*")])
        if path:
            self.rules_path.set(path)

    def on_scan(self) -> None:
        root = self.root_dir.get().strip()
        if not root:
            messagebox.showerror("pls-organize", "Please choose a folder first.")
            return
        files = scan_folder(root)
        self.status.set(f"Scanned {len(files)} files.")
        messagebox.showinfo("pls-organize", f"Scanned {len(files)} files.")

    def on_plan(self) -> None:
        root = self.root_dir.get().strip()
        if not root:
            messagebox.showerror("pls-organize", "Please choose a folder first.")
            return
        rules_file = self.rules_path.get().strip()
        if not os.path.exists(rules_file):
            messagebox.showerror("pls-organize", f"Rules file not found: {rules_file}")
            return

        files = scan_folder(root)
        rules = load_rules_yaml(rules_file)
        plan = build_plan(root, files, rules)

        payload = {
            "root": plan.root,
            "created_at": plan.created_at,
            "operations": [
                {
                    "op": op.op,
                    "from": op.src,
                    "to": op.dst,
                    "reason": op.reason,
                    "confidence": op.confidence,
                }
                for op in plan.operations
            ],
        }
        self.plan = payload
        self._render_plan(payload)
        self.status.set(f"Planned {len(payload['operations'])} ops. Preview shown.")

    def _render_plan(self, payload: dict) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        minc = float(self.min_conf.get())
        ops = payload["operations"]
        shown = 0
        for op in ops:
            conf = float(op["confidence"])
            if conf < minc:
                continue
            self.tree.insert("", "end", values=(
                f"{conf:.2f}",
                op["from"],
                op["to"],
                op["reason"]
            ))
            shown += 1

        self.status.set(f"Preview: showing {shown} ops (min_conf={minc}).")

    def on_apply(self) -> None:
        if not self.plan:
            messagebox.showerror("pls-organize", "No plan yet. Click Plan (Preview) first.")
            return

        # reconstruct minimal Plan object via JSON used by executor wrapper
        from engine.types import Plan, PlannedOp
        ops = []
        for x in self.plan["operations"]:
            ops.append(PlannedOp(
                op=x["op"],
                src=x["from"],
                dst=x["to"],
                reason=x["reason"],
                confidence=float(x["confidence"]),
            ))
        plan_obj = Plan(root=self.plan["root"], created_at=self.plan["created_at"], operations=ops)

        run_id, summary = apply_plan(
            plan=plan_obj,
            journal_dir=self.journal_dir.get(),
            conflict_strategy=self.conflict_strategy.get(),
            min_confidence=float(self.min_conf.get()),
        )
        self.status.set(f"Applied run {run_id}: {summary}")
        messagebox.showinfo("pls-organize", f"Applied run {run_id}\n{summary}")

        # clear plan after apply (optional)
        self.plan = None
        for item in self.tree.get_children():
            self.tree.delete(item)

    def on_undo(self) -> None:
        res = undo_last(self.journal_dir.get())
        if res.get("ok"):
            self.status.set(f"Undo OK: {res}")
            messagebox.showinfo("pls-organize", f"Undo OK\n{res}")
        else:
            self.status.set(f"Undo failed: {res}")
            messagebox.showerror("pls-organize", f"Undo failed\n{res}")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
