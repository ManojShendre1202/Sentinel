"""
Turns Sentinel/config/search_filters.yaml into the actual request
params/body each job source's API expects.

Keep all title/country/location tuning in search_filters.yaml, not here —
this module should only ever need to change when a source's param *names*
change, not when the search criteria change.

Param names verified 2026-08-16 against each source's live docs:
- TheirStack: https://theirstack.com/en/docs/api-reference/jobs/search_jobs_v1
- JobsPipe:   https://docs.jobspipe.dev/api-reference/filters
- Adzuna:     https://developer.adzuna.com/docs/search
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "search_filters.yaml"


def load_filters(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_theirstack_body(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    POST body for TheirStack's /v1/jobs/search endpoint.

    No seniority or salary filter (see search_filters.yaml comments — both
    dropped 2026-08-16 to avoid silently excluding unlabeled postings).
    No city-level location filter: TheirStack requires structured location
    IDs for that (a separate lookup endpoint), not plain text, so Bangalore
    preference is left to the scoring pass for this source. `remote` is
    deprecated in favor of `workplace_types_or`.
    """
    f = filters or load_filters()
    return {
        "job_title_or": f["titles"],
        "job_country_code_or": f["countries"],
        "workplace_types_or": ["remote", "hybrid", "on_site"] if f["include_remote"] else ["hybrid", "on_site"],
        "posted_at_max_age_days": f["posted_max_age_days"],
        "limit": f["page_size"]["theirstack"],
        "blur_company_data": False,
        "include_total_results": False,
    }


def build_jobspipe_params(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Query params for JobsPipe's /v1/jobs/search endpoint
    (api.jobspipe.dev, Bearer auth).

    No seniority or salary filter (see search_filters.yaml). `job_location_or`
    is a substring match, so "Bangalore" is passed alongside `remote: true`
    (JobsPipe ORs these independently — remote listings aren't excluded by
    the city text not matching).
    """
    f = filters or load_filters()
    params: dict[str, Any] = {
        "job_title_or": f["titles"],
        "job_country_code_or": f["countries"],
        "limit": f["page_size"]["jobspipe"],
    }
    if f.get("preferred_locations"):
        params["job_location_or"] = f["preferred_locations"]
    if f.get("include_remote"):
        params["remote"] = True
    return params


def build_adzuna_params(app_id: str, app_key: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Query params for Adzuna's GET /v1/api/jobs/{country}/search/{page}
    endpoint. No salary_min (dropped 2026-08-16, see search_filters.yaml).
    `what` only accepts one query string per call, so callers should loop
    over filters["titles"] and issue one call per title (Adzuna has no
    OR-list param like the other two sources). `where` is set to the first
    preferred location as the primary search; a second unfiltered-location
    call (where=None) should be issued separately to catch remote/other-
    India listings, since Adzuna's `where` narrows rather than ORs with
    remote status.
    """
    f = filters or load_filters()
    params: dict[str, Any] = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": f["page_size"]["adzuna"],
        "max_days_old": f["posted_max_age_days"],
        "sort_by": "date",
    }
    if f.get("preferred_locations"):
        params["where"] = f["preferred_locations"][0]
    return params


def adzuna_titles(filters: dict[str, Any] | None = None) -> list[str]:
    """Adzuna needs one call per title (see build_adzuna_params docstring)."""
    f = filters or load_filters()
    return list(f["titles"])
