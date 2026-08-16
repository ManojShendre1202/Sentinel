"""
Raw fetch for JobsPipe's /v1/jobs/search endpoint (api.jobspipe.dev,
Bearer auth). One call, no pagination.

No live usage-check endpoint exists for JobsPipe (confirmed against their
docs) — request failures (incl. quota/rate-limit responses) are caught and
raised as SourceFetchError instead of crashing the whole fetch run.
"""
import requests

from sources import SourceFetchError
from sources.query_builder import build_jobspipe_params, load_filters

URL = "https://api.jobspipe.dev/v1/jobs/search"


def fetch(api_key: str) -> list[dict]:
    params = build_jobspipe_params(load_filters())
    try:
        r = requests.post(
            URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=params,
            timeout=30,
        )
        r.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise SourceFetchError(f"jobspipe: request failed: {exc}") from exc

    return r.json().get("data", [])
