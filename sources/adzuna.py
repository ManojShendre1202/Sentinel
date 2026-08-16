"""
Raw fetch for Adzuna's GET /v1/api/jobs/in/search/1 endpoint. One call per
title (Adzuna has no OR-list param), results concatenated.

No live usage-check endpoint exists for Adzuna either — same reactive
error handling as jobspipe.py. If a title-call fails, the ones already
fetched are kept and the failure is raised after the loop (so one bad
title doesn't silently drop results from titles that succeeded first).
"""
import requests

from sources import SourceFetchError
from sources.query_builder import adzuna_titles, build_adzuna_params, load_filters

URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"


def fetch(app_id: str, app_key: str) -> list[dict]:
    filters = load_filters()
    jobs: list[dict] = []
    for title in adzuna_titles(filters):
        params = build_adzuna_params(app_id, app_key, filters)
        params["what"] = title
        try:
            r = requests.get(URL, params=params, timeout=30)
            r.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise SourceFetchError(f"adzuna: request failed on title '{title}': {exc}", partial_results=jobs) from exc
        jobs.extend(r.json().get("results", []))
    return jobs
