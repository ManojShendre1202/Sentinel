"""
Raw fetch for Adzuna's GET /v1/api/jobs/in/search/1 endpoint. Two calls per
title (Adzuna has no OR-list param, and `where` narrows rather than ORs
with remote status): one scoped to preferred_locations[0], one unfiltered
(where=None) to catch remote/other-India listings. Results concatenated
and deduped by job id, since the unfiltered call can re-return
Bangalore-located jobs already fetched by the scoped call.

No live usage-check endpoint exists for Adzuna either — same reactive
error handling as jobspipe.py. If a call fails, the ones already fetched
are kept and the failure is raised after the loop (so one bad call
doesn't silently drop results from calls that succeeded first).
"""
import requests

from backend.sources import SourceFetchError
from backend.sources.query_builder import adzuna_titles, build_adzuna_params, load_filters

URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"


def fetch(app_id: str, app_key: str) -> list[dict]:
    filters = load_filters()
    jobs: list[dict] = []
    seen_ids: set[str] = set()

    def _run(title: str, where: str | None, label: str) -> None:
        params = build_adzuna_params(app_id, app_key, filters)
        params["what"] = title
        if where is None:
            params.pop("where", None)
        try:
            r = requests.get(URL, params=params, timeout=30)
            r.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise SourceFetchError(f"adzuna: request failed on title '{title}' ({label}): {exc}", partial_results=jobs) from exc
        for job in r.json().get("results", []):
            job_id = job.get("id")
            if job_id is not None and job_id in seen_ids:
                continue
            if job_id is not None:
                seen_ids.add(job_id)
            jobs.append(job)

    for title in adzuna_titles(filters):
        _run(title, filters.get("preferred_locations", [None])[0], "scoped")
        if filters.get("include_remote"):
            _run(title, None, "unfiltered")

    return jobs
