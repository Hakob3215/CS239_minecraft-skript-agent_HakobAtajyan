from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional
from agent_system.paths import DATA_DIR

DB_PATH = DATA_DIR / "skript_knowledge.db"

# Non-alphanumeric characters to strip (leaving only words and numbers)
CLEAN_PUNCT_REGEX = re.compile(r"[^a-zA-Z0-9_]")

# English & Minecraft conversational stop words to filter out
STOP_WORDS = {
    "a", "about", "above", "after", "again", "all", "also", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "could", "did", "do", "does", "doing",
    "down", "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "s",
    "same", "she", "should", "so", "some", "such", "t", "than", "that", "the",
    "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom", "why", "will",
    "with", "you", "your", "yours", "yourself", "yourselves",
    # Trigger and command boilerplate
    "create", "update", "fix", "add", "make", "change", "remove", "delete"
}


def sanitize_fts_query(query: str) -> str:
    """
    Cleans conversational input into an FTS5 OR query:
    1. Replaces all punctuation with spaces.
    2. Drops stop words and duplicates.
    3. Joins relevant keywords with OR so BM25 ranks the best matches first.
    """
    cleaned = CLEAN_PUNCT_REGEX.sub(" ", query)
    raw_tokens = [w.strip().lower() for w in cleaned.split() if w.strip()]

    # Filter stop words while preserving order and uniqueness
    seen = set()
    filtered_tokens = []
    for token in raw_tokens:
        if token not in STOP_WORDS and token not in seen and len(token) > 1:
            seen.add(token)
            filtered_tokens.append(token)

    # Fallback if the prompt consisted entirely of stop words
    tokens_to_use = filtered_tokens if filtered_tokens else raw_tokens[:5]
    if not tokens_to_use:
        return ""

    # Cap at top 8 key terms to keep FTS5 evaluation fast and high-precision
    tokens_to_use = tokens_to_use[:8]

    # Join with OR so any matching keyword is retrieved and ranked by BM25
    return " OR ".join(f'"{token}"' for token in tokens_to_use)


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
            patterns_str = "\n    ".join(h["patterns"]) if h["patterns"] else "None"
            examples_str = "\n    ".join(h["examples"]) if h["examples"] else "None"
            block = (
                f"### [{h['category'].upper()}] {h['name']} (`{h['id']}`)\n"
                f"- **Patterns**:\n    {patterns_str}\n"
                f"- **Description**: {h['description']}\n"
                f"- **Examples**:\n    {examples_str}"
            )
            blocks.append(block)

        return "\n\n".join(blocks)