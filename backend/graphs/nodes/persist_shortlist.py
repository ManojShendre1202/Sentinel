"""
Graph 1, node 5 — persist_shortlist.

Parses results.json and writes Shortlist rows (one per scored JobListing,
overwrite-in-place on re-evaluation — no history table).
"""
import json

from backend.core.models import JobListing, Shortlist


def persist_results(results_json_path: str) -> int:
    with open(results_json_path, encoding="utf-8") as f:
        results = json.load(f)["results"]

    count = 0
    for item in results:
        job = JobListing.objects.get(pk=item["job_listing_id"])
        Shortlist.objects.update_or_create(
            job=job,
            defaults={
                "status": item["status"],
                "match_score": item["match_score"],
                "dimension_scores": item["dimension_scores"],
                "reasoning": item["reasoning"],
            },
        )
        count += 1
    return count
