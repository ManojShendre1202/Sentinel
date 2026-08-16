"""
Graph 1, node 2 — normalize_and_store_jobs.

Normalizes each {"source", "raw"} dict via sources/normalize.py, drops
discards (no apply URL), upserts into JobListing on (source, external_id).
"""
from core.models import JobListing
from sources.normalize import normalize_adzuna, normalize_jobspipe, normalize_theirstack

NORMALIZERS = {
    "theirstack": normalize_theirstack,
    "jobspipe": normalize_jobspipe,
    "adzuna": normalize_adzuna,
}


def normalize_and_dedup(raw_jobs: list[dict]) -> list[dict]:
    normalized = []
    for item in raw_jobs:
        canonical = NORMALIZERS[item["source"]](item["raw"])
        if canonical is None:
            continue
        job_listing, _ = JobListing.objects.update_or_create(
            source=canonical["source"],
            external_id=canonical["external_id"],
            defaults={
                "title": canonical["title"],
                "company": canonical["company"],
                "location": canonical["location"],
                "remote": canonical["remote"],
                "url": canonical["url"],
                "description": canonical["description"],
                "signals": canonical["signals"],
                "raw_payload": canonical["raw_payload"],
            },
        )
        canonical["job_listing_id"] = job_listing.pk
        normalized.append(canonical)
    return normalized
