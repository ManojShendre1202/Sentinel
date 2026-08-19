"""
Graph 1, node 1 — fetch_jobs.

Calls sources/{theirstack,jobspipe,adzuna}.py in parallel using keys from
django settings (IS_DEV-aware). One source's SourceFetchError (quota
guardrail trip or request failure) doesn't take down the other two —
failures are collected and returned alongside whatever jobs did come back
(incl. partial_results from a mid-run failure).
"""
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings

from backend.sources import SourceFetchError, adzuna, jobspipe, theirstack


def fetch_all() -> tuple[list[dict], list[str]]:
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            "theirstack": pool.submit(theirstack.fetch, settings.THEIRSTACK_API_KEY),
            "jobspipe": pool.submit(jobspipe.fetch, settings.JOBSPIPE_API_KEY),
            "adzuna": pool.submit(adzuna.fetch, settings.ADZUNA_ID, settings.ADZUNA_API_KEY),
        }

        results = []
        errors = []
        for source, future in futures.items():
            try:
                results.append((source, future.result()))
            except SourceFetchError as exc:
                errors.append(str(exc))
                results.append((source, exc.partial_results))

    raw_jobs = [{"source": source, "raw": raw} for source, raws in results for raw in raws]
    return raw_jobs, errors
