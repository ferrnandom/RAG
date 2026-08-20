"""shared helpers for the evaluation"""

import json
import subprocess
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).parent


def chunk_key(metadata: dict[str, Any]) -> str:
    """Because postgres ids are generated always as identity, they change everytime we re-ingest. To get more reliable ids, we'll create a composite key from
    their metadata"""
    return f"{Path(metadata['source']).name}::{metadata['chunk_index']}"


def rows_to_keys(rows: list[dict[str, Any]]) -> list[str]:
    """We convert retrieval results into ranked chunk keys"""
    keys = []
    for row in rows:
        keys.append(chunk_key(row["metadata"]))
    return keys


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        lines = []
        for line in f:
            if line.strip():
                lines.append(json.loads(line))
        return lines


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(
            json.dumps(record, ensure_ascii=False) + "\n" for record in records
        )


def git_sha() -> str:
    """commit hash, or 'uncommitted' if the repo has no commits yet"""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "uncommitted"
