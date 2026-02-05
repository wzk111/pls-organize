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