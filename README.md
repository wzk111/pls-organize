# pls-organize

pls-organize is a preview-first, rollback-safe file organizer with AI-generated rules.

It helps you clean up messy folders using deterministic planning, human approval,
and optional natural-language instructions — without ever blindly touching your files.

## Design Principles
- Preview-first: nothing happens without your approval
- Deterministic execution: plans are generated and validated before execution
- Human-in-the-loop AI: LLMs suggest rules, the engine decides moves
- Transactional safety: every operation can be undone (journal)
- Separation of concerns: scan → plan → apply → rollback

## Quick Start
```bash
pip install -r requirements.txt

python -m cli.main scan "/path/to/folder" -o scan.json
python -m cli.main plan "/path/to/folder" --rules rules.sample.yaml -o plan.json
python -m cli.main apply plan.json --journal .pls-organize-journal
python -m cli.main undo --journal .pls-organize-journal
```
## App GUI
```bash
python -m gui.app
```

## App UI Walkthrough

pls-organize follows a simple, explicit 3-step workflow to ensure safety and clarity.

### 1. Select Folder & Rules
At the top of the UI, choose the target folder to organize and the rules file (`rules.yaml`).

Optionally, you can describe your intent using natural language (e.g. *“Sort screenshots by month and put PDFs into Documents”*).
Click **Generate rules** to let the AI draft a rules file — no files are moved at this stage.

---

### 2. Scan
Click **Scan** to analyze the folder.
This step only collects metadata (file names, extensions, timestamps) and does not modify anything.

---

### 3. Plan (Preview)
Click **Plan (Preview)** to generate a deterministic move plan based on the rules.

The preview table shows:
- **From**: current file location
- **To**: proposed destination
- **Confidence**: how certain the rule match is
- **Reason**: which rule caused the action

You can filter the preview using:
- Minimum confidence threshold
- Search
- Low-confidence toggle

This makes every action explainable and reviewable before execution.

---

### 4. Apply
Click **Apply** to execute the plan.
Only the currently previewed operations are applied.

All operations are written to a journal, enabling safe rollback.

---

### 5. Undo
Click **Undo last** to revert the most recent apply:
- Files are moved back to their original locations
- Empty directories created during apply are removed

This guarantees filesystem safety and reversibility.
