from __future__ import annotations
import os
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
        self.geometry("1100x720")
        self.minsize(980, 640)

        # ttk theme (on Windows this helps a lot)
        style = ttk.Style(self)
        style.configure("Step.TButton", font=("Segoe UI", 9))
        style.configure("ActiveStep.TButton", font=("Segoe UI", 9, "bold"))
        try:
            style.theme_use("vista")
        except Exception:
            pass

        # Variables
        self.root_dir = tk.StringVar(value="")
        self.rules_path = tk.StringVar(value="rules.generated.yaml")
        self.journal_dir = tk.StringVar(value=".pls-organize-journal")
        self.conflict_strategy = tk.StringVar(value="rename")

        # Filters
        self.min_conf = tk.DoubleVar(value=0.50)  # default more “safe”
        self.search_text = tk.StringVar(value="")
        self.only_low = tk.BooleanVar(value=False)

        # Data
        self.plan_payload: dict | None = None
        self.all_rows_cache: list[dict] = []  # operations cache for filtering
        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        # Header
        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text="pls-organize", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(header, text="Preview-first • Rollback-safe • Human-in-the-loop", foreground="#555").pack(side="left", padx=12)

        # --- Top input area (two columns) ---
        top = ttk.Frame(root)
        top.pack(fill="x", pady=(10, 8))

        left = ttk.Frame(top)
        left.pack(side="left", fill="x", expand=True)

        right = ttk.Frame(top)
        right.pack(side="right", fill="y")

        # Folder row
        row1 = ttk.Frame(left)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="Folder", width=12).pack(side="left")
        ttk.Entry(row1, textvariable=self.root_dir).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(row1, text="Browse", command=self.on_browse).pack(side="left")

        # Rules row
        row2 = ttk.Frame(left)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Rules file", width=12).pack(side="left")
        ttk.Entry(row2, textvariable=self.rules_path).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(row2, text="Load rules", command=self.on_load_rules).pack(side="left")

        # Natural language + Generate rules (aligned)
        nl_frame = ttk.Frame(left)
        nl_frame.pack(fill="x", pady=(8, 2))

        ttk.Label(nl_frame, text="Natural language intent", width=18)\
            .grid(row=0, column=0, sticky="nw")

        self.nl = tk.Text(nl_frame, height=4)
        self.nl.grid(row=0, column=1, sticky="we", padx=(6, 6))

        ttk.Button(
            nl_frame,
            text="✨ Generate rules",
            command=self.on_generate_rules
        ).grid(row=0, column=2, sticky="n")

        nl_frame.columnconfigure(1, weight=1)

        # --- Controls row ---
        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(6, 10))

        ttk.Label(controls, text="Conflict").pack(side="left")
        ttk.Combobox(controls, textvariable=self.conflict_strategy, values=["rename", "skip", "overwrite"], width=12, state="readonly").pack(side="left", padx=(6, 14))

        ttk.Label(controls, text="Min confidence").pack(side="left")
        ttk.Scale(controls, from_=0.0, to=1.0, orient="horizontal", variable=self.min_conf, command=lambda _=None: self._apply_filters()).pack(side="left", padx=(6, 6))
        self.min_conf_label = ttk.Label(controls, text=f"{self.min_conf.get():.2f}")
        self.min_conf_label.pack(side="left", padx=(0, 14))

        ttk.Label(controls, text="Search").pack(side="left")
        search_entry = ttk.Entry(controls, textvariable=self.search_text, width=22)
        search_entry.pack(side="left", padx=(6, 14))
        search_entry.bind("<KeyRelease>", lambda e: self._apply_filters())

        ttk.Checkbutton(controls, text="Only low-confidence", variable=self.only_low, command=self._apply_filters).pack(side="left")

        ttk.Label(controls, text="Journal").pack(side="left", padx=(14, 0))
        ttk.Entry(controls, textvariable=self.journal_dir, width=22).pack(side="left", padx=(6, 0))

        # --- Step buttons ---
        steps = ttk.Frame(root)
        steps.pack(fill="x", pady=(0, 10))

        # ttk.Button(steps, text="1) Scan", command=self.on_scan).pack(side="left")
        # ttk.Button(steps, text="2) Plan (Preview)", command=self.on_plan).pack(side="left", padx=8)
        # ttk.Button(steps, text="3) Apply", command=self.on_apply).pack(side="left", padx=8)
        # ttk.Button(steps, text="Undo last", command=self.on_undo).pack(side="left", padx=8)

        self.btn_scan = ttk.Button(steps, text="🔍 Scan", command=self.on_scan)
        self.btn_scan.pack(side="left")

        self.btn_plan = ttk.Button(steps, text="🧠 Plan (Preview)", command=self.on_plan)
        self.btn_plan.pack(side="left", padx=8)

        self.btn_apply = ttk.Button(steps, text="🚀 Apply", command=self.on_apply)
        self.btn_apply.pack(side="left", padx=8)

        self.btn_undo = ttk.Button(steps, text="↩ Undo last", command=self.on_undo)
        self.btn_undo.pack(side="left", padx=8)


        # --- Summary cards ---
        cards = ttk.Frame(root)
        cards.pack(fill="x", pady=(0, 10))

        self.card_total = self._make_card(cards, "Planned ops", "0")
        self.card_high = self._make_card(cards, "High (≥0.7)", "0")
        self.card_mid = self._make_card(cards, "Mid (0.4–0.69)", "0")
        self.card_low = self._make_card(cards, "Low (<0.4)", "0")
        self.card_shown = self._make_card(cards, "Shown (filtered)", "0")

        # --- Table area ---
        table_wrap = ttk.Frame(root)
        table_wrap.pack(fill="both", expand=True)

        cols = ("confidence", "from", "to", "reason")
        self.tree = ttk.Treeview(table_wrap, columns=cols, show="headings", height=18)
        self.tree.heading("confidence", text="Conf")
        self.tree.heading("from", text="From")
        self.tree.heading("to", text="To")
        self.tree.heading("reason", text="Reason")

        self.tree.column("confidence", width=70, anchor="center")
        self.tree.column("from", width=420)
        self.tree.column("to", width=420)
        self.tree.column("reason", width=200)

        # Nice tags
        self.tree.tag_configure("row_a", background="#FAFAFA")
        self.tree.tag_configure("row_b", background="#FFFFFF")
        self.tree.tag_configure("high", foreground="#0B6E4F")
        self.tree.tag_configure("mid", foreground="#8A6D00")
        self.tree.tag_configure("low", foreground="#B00020")

        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=yscroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        # Status bar
        self.status = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(root, textvariable=self.status, foreground="#444")
        status_bar.pack(fill="x", pady=(10, 0))

    def _make_card(self, parent: ttk.Frame, title: str, value: str) -> ttk.Label:
        frame = ttk.Frame(parent, padding=(10, 8))
        frame.pack(side="left", padx=(0, 10), fill="x", expand=True)
        ttk.Label(frame, text=title, foreground="#666").pack(anchor="w")
        lbl = ttk.Label(frame, text=value, font=("Segoe UI", 14, "bold"))
        lbl.pack(anchor="w")
        return lbl

    # ---------------- Helpers ----------------
    def _set_active_step(self, step: str):
        self.btn_scan.configure(style="Step.TButton")
        self.btn_plan.configure(style="Step.TButton")
        self.btn_apply.configure(style="Step.TButton")

        if step == "scan":
            self.btn_scan.configure(style="ActiveStep.TButton")
        elif step == "plan":
            self.btn_plan.configure(style="ActiveStep.TButton")
        elif step == "apply":
            self.btn_apply.configure(style="ActiveStep.TButton")

    def _short_path(self, p: str, keep: int = 26) -> str:
        """Keep head + tail, compress middle to make plan readable."""
        if len(p) <= keep * 2 + 5:
            return p
        return p[:keep] + " … " + p[-keep:]

    def _update_cards(self, ops: list[dict]) -> None:
        total = len(ops)
        high = sum(1 for o in ops if float(o["confidence"]) >= 0.7)
        mid = sum(1 for o in ops if 0.4 <= float(o["confidence"]) < 0.7)
        low = sum(1 for o in ops if float(o["confidence"]) < 0.4)

        self.card_total.config(text=str(total))
        self.card_high.config(text=str(high))
        self.card_mid.config(text=str(mid))
        self.card_low.config(text=str(low))

    def _apply_filters(self) -> None:
        if not self.plan_payload:
            return

        minc = float(self.min_conf.get())
        self.min_conf_label.config(text=f"{minc:.2f}")

        q = self.search_text.get().strip().lower()
        only_low = bool(self.only_low.get())

        filtered = []
        for op in self.all_rows_cache:
            conf = float(op["confidence"])
            if conf < minc:
                continue

            if only_low and conf >= 0.4:
                continue

            if q:
                hay = (op["from"] + " " + op["to"] + " " + op.get("reason", "")).lower()
                if q not in hay:
                    continue

            filtered.append(op)

        self._render_table(filtered)
        self.card_shown.config(text=str(len(filtered)))
        self.status.set(f"Preview: {len(filtered)} ops shown (min_conf={minc:.2f})")

    def _render_table(self, ops: list[dict]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, op in enumerate(ops):
            conf = float(op["confidence"])
            # Color tag
            if conf >= 0.7:
                conf_tag = "high"
            elif conf >= 0.4:
                conf_tag = "mid"
            else:
                conf_tag = "low"

            zebra = "row_a" if idx % 2 == 0 else "row_b"

            self.tree.insert(
                "",
                "end",
                values=(
                    f"{conf:.2f}",
                    self._short_path(op["from"]),
                    self._short_path(op["to"]),
                    op.get("reason", ""),
                ),
                tags=(zebra, conf_tag),
            )

    # ---------------- Actions ----------------
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
        messagebox.showinfo("pls-organize", f"Generated rules saved to:\n{self.rules_path.get()}")

    def on_load_rules(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("YAML", "*.yaml *.yml"), ("All", "*.*")])
        if path:
            self.rules_path.set(path)

    def on_scan(self) -> None:
        self._set_active_step("scan")
        root = self.root_dir.get().strip()
        if not root:
            messagebox.showerror("pls-organize", "Please choose a folder first.")
            return
        files = scan_folder(root)
        self.status.set(f"Scanned {len(files)} files.")
        messagebox.showinfo("pls-organize", f"Scanned {len(files)} files.")

    def on_plan(self) -> None:
        self._set_active_step("plan")
        root = self.root_dir.get().strip()
        if not root:
            messagebox.showerror("pls-organize", "Please choose a folder first.")
            return
        rules_file = self.rules_path.get().strip()
        if not os.path.exists(rules_file):
            messagebox.showerror("pls-organize", f"Rules file not found:\n{rules_file}")
            return

        files = scan_folder(root)
        rules = load_rules_yaml(rules_file)
        plan = build_plan(root, files, rules)  # unmatched files are skipped by planner (your updated logic)

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
        self.plan_payload = payload
        self.all_rows_cache = payload["operations"]

        self._update_cards(self.all_rows_cache)
        self._apply_filters()

    def on_apply(self) -> None:
        self._set_active_step("apply")
        if not self.plan_payload:
            messagebox.showerror("pls-organize", "No plan yet. Click Plan (Preview) first.")
            return

        from engine.types import Plan, PlannedOp

        ops = []
        for x in self.plan_payload["operations"]:
            ops.append(
                PlannedOp(
                    op=x["op"],
                    src=x["from"],
                    dst=x["to"],
                    reason=x["reason"],
                    confidence=float(x["confidence"]),
                )
            )
        plan_obj = Plan(root=self.plan_payload["root"], created_at=self.plan_payload["created_at"], operations=ops)

        run_id, summary = apply_plan(
            plan=plan_obj,
            journal_dir=self.journal_dir.get(),
            conflict_strategy=self.conflict_strategy.get(),
            min_confidence=float(self.min_conf.get()),
        )
        self.status.set(f"Applied run {run_id}: moved={summary['moved']} skipped={summary['skipped']} errors={summary['errors']}")
        messagebox.showinfo("pls-organize", f"Applied run {run_id}\n{summary}")

        # clear plan
        self.plan_payload = None
        self.all_rows_cache = []
        self._render_table([])
        self._update_cards([])
        self.card_shown.config(text="0")

    def on_undo(self) -> None:
        res = undo_last(self.journal_dir.get())
        if res.get("ok"):
            self.status.set(f"Undo OK: undone={res.get('undone', 0)} dirs_deleted={res.get('dirs_deleted', 0)}")
            messagebox.showinfo("pls-organize", f"Undo OK\n{res}")
        else:
            self.status.set(f"Undo failed: {res}")
            messagebox.showerror("pls-organize", f"Undo failed\n{res}")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
