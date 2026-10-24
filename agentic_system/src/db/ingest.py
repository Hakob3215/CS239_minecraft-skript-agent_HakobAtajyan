import html
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List

DOCS_PATH = Path("data/docs.json")
MANIFEST_OUTPUT_PATH = Path("data/event_manifest.json")
DB_OUTPUT_PATH = Path("data/skript_knowledge.db")

TAG_RE = re.compile(r"<[^>]+>")

# Syntax categories from docs.json to index for SWE retrieval
SYNTAX_CATEGORIES = [
    "conditions",
    "effects",
    "expressions",
    "types",
    "functions",
    "structures",
    "sections",
]

def normalize_text(field: Any) -> str:
    """Normalizes descriptions: flattens lists, strips HTML tags, and unescapes entities."""
    if not field:
        return ""
    if isinstance(field, list):
        text = " ".join(str(item).strip() for item in field if item)
    else:
        text = str(field).strip()

    clean = TAG_RE.sub("", text)
    clean = html.unescape(clean)
    return " ".join(clean.split())

def normalize_list(field: Any) -> str:
    """Normalizes patterns or examples into a clean newline-delimited string."""
    if not field:
        return ""
    if isinstance(field, list):
        return "\n".join(str(item).strip() for item in field if item)
    return str(field).strip()

def build_event_manifest(docs: Dict[str, Any]):
    """Extracts lightweight event definitions from docs.json for the Secretary agent."""
    raw_events = docs.get("events", [])
    manifest: List[Dict[str, Any]] = []

    for evt in raw_events:
        manifest.append({
            "id": evt.get("id"),
            "name": evt.get("name"),
            "patterns": evt.get("patterns", []),
            "description": normalize_text(evt.get("description")),
        })

    MANIFEST_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Generated {MANIFEST_OUTPUT_PATH} ({len(manifest)} events, {MANIFEST_OUTPUT_PATH.stat().st_size / 1024:.2f} KB)")

def build_fts_database(docs: Dict[str, Any]):
    """Compiles syntax patterns and descriptions into an SQLite FTS5 table."""
    DB_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing DB file for a clean rebuild
    if DB_OUTPUT_PATH.exists():
        DB_OUTPUT_PATH.unlink()

    conn = sqlite3.connect(DB_OUTPUT_PATH)
    cursor = conn.cursor()

    # Create FTS5 virtual table
    cursor.execute("""
        CREATE VIRTUAL TABLE skript_docs USING fts5(
            id UNINDEXED,
            category UNINDEXED,
            name,
            patterns,
            description,
            examples
        );
    """)

    total_inserted = 0

    for category in SYNTAX_CATEGORIES:
        items = docs.get(category, [])
        for item in items:
            doc_id = item.get("id", "")
            name = item.get("name", "")
            patterns = normalize_list(item.get("patterns", []))
            description = normalize_text(item.get("description"))
            examples = normalize_list(item.get("examples", []))

            cursor.execute(
                """
                INSERT INTO skript_docs (id, category, name, patterns, description, examples)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, category, name, patterns, description, examples),
            )
            total_inserted += 1

    conn.commit()
    conn.close()

    print(f"Generated {DB_OUTPUT_PATH} ({total_inserted} entries, {DB_OUTPUT_PATH.stat().st_size / 1024:.2f} KB)")

def main():
    if not DOCS_PATH.exists():
        raise FileNotFoundError(f"Missing documentation file: {DOCS_PATH}")

    print(f"Reading {DOCS_PATH}...")
    with open(DOCS_PATH, "r", encoding="utf-8") as f:
        docs = json.load(f)

    build_event_manifest(docs)
    build_fts_database(docs)

if __name__ == "__main__":
    main()