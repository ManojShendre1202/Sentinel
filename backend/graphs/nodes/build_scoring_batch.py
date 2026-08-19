"""
Graph 1, node 3 — build_scoring_batch.

Writes batch.json: each normalized job's scoring-relevant fields (no
raw_payload — too noisy, signals already curated for this) + a pointer to
profile.md for score_with_claude.py to read directly rather than duplicating
profile text into every batch.
"""
import json
from pathlib import Path

BATCH_DIR = Path(__file__).resolve().parent.parent / "batch_data"
BATCH_PATH = BATCH_DIR / "batch.json"
PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "profile.md"

BATCH_FIELDS = ["job_listing_id", "source", "title", "company", "location", "remote", "url", "description", "signals"]


def build_batch_json(normalized_jobs: list[dict]) -> str:
    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    batch = {
        "profile_path": str(PROFILE_PATH),
        "jobs": [{field: job[field] for field in BATCH_FIELDS} for job in normalized_jobs],
    }

    BATCH_PATH.write_text(json.dumps(batch, indent=2), encoding="utf-8")
    return str(BATCH_PATH)
