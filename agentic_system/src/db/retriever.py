from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional

DB_PATH = Path("data/skript_knowledge.db")

# Regex to strip characters that break SQLite FTS5 query syntax
FTS_SPECIAL_CHARS = re.compile(r'["*^:()\[\]{}]')


def sanitize_fts_query(query: str) -> str:
    """
    Cleans raw input text to ensure it is valid SQLite FTS5 syntax.
    Extracts alphanumeric words and joins them with implicit AND.
    """
    cleaned = FTS_SPECIAL_CHARS.sub(" ", query)
    tokens = [word.strip() for word in cleaned.split() if word.strip()]
    if not tokens:
        return ""
    # Wrap each token in double quotes to prevent collision with FTS boolean operators
    return " ".join(f'"{token}"' for token in tokens)


class DocRetriever:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Executes a BM25 ranked full-text search against skript_docs.
        Optionally filters by category (e.g. 'effects', 'conditions', 'expressions').
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Knowledge database not found at {self.db_path}")

        safe_query = sanitize_fts_query(query)
        if not safe_query:
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if category:
            sql = """
                SELECT id, category, name, patterns, description, examples, bm25(skript_docs) AS rank
                FROM skript_docs
                WHERE skript_docs MATCH ? AND category = ?
                ORDER BY rank
                LIMIT ?;
            """
            cursor.execute(sql, (safe_query, category.lower(), limit))
        else:
            sql = """
                SELECT id, category, name, patterns, description, examples, bm25(skript_docs) AS rank
                FROM skript_docs
                WHERE skript_docs MATCH ?
                ORDER BY rank
                LIMIT ?;
            """
            cursor.execute(sql, (safe_query, limit))

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "category": row[1],
                "name": row[2],
                "patterns": row[3].split("\n") if row[3] else [],
                "description": row[4],
                "examples": row[5].split("\n") if row[5] else [],
                "rank": row[6],
            })
        return results

    def format_for_prompt(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 4,
    ) -> str:
        """
        Retrieves search hits and converts them into a markdown text block
        tailored for the SWE Agent's context prompt.
        """
        hits = self.search(query, category=category, limit=limit)
        if not hits:
            return f"No documentation found for query: '{query}'"

        blocks = []
        for h in hits:
            patterns_str = "\n  ".join(h["patterns"]) if h["patterns"] else "None"
            examples_str = "\n  ".join(h["examples"]) if h["examples"] else "None"
            block = (
                f"### [{h['category'].upper()}] {h['name']} (`{h['id']}`)\n"
                f"- **Patterns**:\n  {patterns_str}\n"
                f"- **Description**: {h['description']}\n"
                f"- **Examples**:\n  {examples_str}"
            )
            blocks.append(block)

        return "\n\n".join(blocks)