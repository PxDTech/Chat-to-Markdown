from pathlib import Path
import json
import re
from datetime import datetime

# ---- Config ----
INPUT_JSON = Path("conversations.json")
OUTPUT_DIR = Path("ChatGPT_Backup")
ADD_DATE_PREFIX_TO_FILENAME = (
    False  # keep filenames simple; set True if you want YYYY-MM-DD prefix
)

OUTPUT_DIR.mkdir(exist_ok=True)


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100] or "Untitled"


def yaml_escape(value: str) -> str:
    """Safely quote YAML scalars."""
    if value is None:
        return ""
    text = str(value)
    # Quote if special characters or leading/trailing spaces present
    if re.search(r'[:\-\?\[\]\{\},&\*#\!\|>\'%@`"]|\s$', text) or text.startswith(
        (" ", "-", "?", ":", "@")
    ):
        # Escape double quotes inside
        return '"' + text.replace('"', '\\"') + '"'
    return text


def iso_date(dt_str: str) -> str:
    """Return a normalized ISO date (YYYY-MM-DD) from export's create_time when possible."""
    if not dt_str:
        return ""
    try:
        # Export uses ISO-like timestamps; be liberal in parsing
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return ""


with open(INPUT_JSON, "r", encoding="utf-8") as f:
    conversations = json.load(f)

exported = 0
for convo in conversations:
    title = convo.get("title") or "Untitled"
    created_raw = convo.get("create_time", "")
    created_date = iso_date(created_raw)
    convo_id = convo.get("id") or convo.get("conversation_id") or ""

    # Collect messages in order
    mapping = convo.get("mapping", {}) or {}
    # mapping is a dict keyed by node ids; we’ll try to respect the inherent order if present,
    # otherwise fallback to values() order.
    nodes = list(mapping.values())

    messages = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        msg = node.get("message")
        if not isinstance(msg, dict):
            continue

        role = (msg.get("author") or {}).get("role") or ""
        # Skip tool/system messages; keep only user/assistant
        if role not in {"user", "assistant"}:
            continue

        content = msg.get("content") or {}
        # V1 style: parts = [string, ...]
        parts = content.get("parts")
        text = ""
        if isinstance(parts, list) and parts:
            text = "\n\n".join(str(p) for p in parts).strip()
        # Fallbacks: some exports store text at different keys
        if not text:
            text = (content.get("text") or "").strip()

        if not text:
            continue

        if role == "user":
            messages.append(f"**User:**\n{text}\n")
        else:
            messages.append(f"**Assistant:**\n{text}\n")

    # Build YAML front-matter
    yaml_lines = [
        "---",
        f"title: {yaml_escape(title)}",
        f"date: {yaml_escape(created_date) if created_date else '\"\"'}",
        "tags: [chatgpt, export]",
        "participants: [user, assistant]",
        f"source: chatgpt",
        (
            f"conversation_id: {yaml_escape(convo_id)}"
            if convo_id
            else 'conversation_id: ""'
        ),
        "---",
        "",
    ]

    body = f"# {title}\n\n"
    if created_raw:
        body += f"*Created:* {created_raw}\n\n"
    body += "\n---\n\n".join(messages) if messages else "_No messages found._"

    md_content = "\n".join(yaml_lines) + body

    # Filename
    base = sanitize_filename(title)
    if ADD_DATE_PREFIX_TO_FILENAME and created_date:
        base = f"{created_date} {base}"
    outfile = OUTPUT_DIR / f"{base}.md"
    outfile.write_text(md_content, encoding="utf-8")
    exported += 1

print(f"✅ Exported {exported} conversations to {OUTPUT_DIR.resolve()}")
