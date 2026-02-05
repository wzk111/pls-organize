from __future__ import annotations
import os
import re
import yaml

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompt.txt")


def _load_prompt() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _fallback_rules(user_input: str) -> dict:
    """
    Simple heuristic fallback when no API key is available.
    Generates a few safe, common rules.
    """
    text = user_input.lower()

    rules = []

    # screenshots
    if "screenshot" in text or "截图" in user_input or "截屏" in user_input:
        rules.append({
            "name": "screenshots_by_month",
            "match": {"extension": [".png", ".jpg", ".jpeg"], "filename_contains": ["screenshot", "截屏", "截图"]},
            "action": {"move_to": "Screenshots/{year}/{month}"}
        })

    # installers
    if "installer" in text or "安装" in user_input or "setup" in text:
        rules.append({
            "name": "installers",
            "match": {"extension": [".exe", ".msi", ".dmg", ".pkg"], "filename_contains": []},
            "action": {"move_to": "Installers"}
        })

    # pdf docs
    if "pdf" in text or "document" in text or "文档" in user_input:
        rules.append({
            "name": "pdf_documents",
            "match": {"extension": [".pdf"], "filename_contains": []},
            "action": {"move_to": "Documents/PDF"}
        })

    # archives
    if "zip" in text or "archive" in text or "压缩" in user_input:
        rules.append({
            "name": "archives",
            "match": {"extension": [".zip", ".rar", ".7z", ".tar", ".gz"], "filename_contains": []},
            "action": {"move_to": "Archives"}
        })

    if not rules:
        # default safe set
        rules = [{
            "name": "images",
            "match": {"extension": [".png", ".jpg", ".jpeg", ".webp"], "filename_contains": []},
            "action": {"move_to": "Images"}
        }]

    return {"rules": rules}


def generate_rules_yaml(user_input: str) -> str:
    """
    Returns YAML string (rules.yaml content).
    Uses OpenAI if OPENAI_API_KEY is set, otherwise fallback.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return yaml.safe_dump(_fallback_rules(user_input), sort_keys=False, allow_unicode=True)

    # OpenAI path
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = _load_prompt().replace("{{USER_INPUT}}", user_input)

        # Keep it simple and cheap
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[
                {"role": "system", "content": "You output YAML only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = resp.choices[0].message.content or ""
        # Basic guard: ensure it looks like YAML with 'rules:'
        if "rules:" not in content:
            return yaml.safe_dump(_fallback_rules(user_input), sort_keys=False, allow_unicode=True)
        return content.strip()
    except Exception:
        return yaml.safe_dump(_fallback_rules(user_input), sort_keys=False, allow_unicode=True)
