class SourceFetchError(Exception):
    """Raised by any sources/*.py fetch() on a request failure or quota
    guardrail trip. Caught per-source in graphs/nodes/fetch_jobs.py so one
    source failing doesn't take down the other two.

    `partial_results` carries whatever was already fetched before the
    failure (e.g. Adzuna succeeding on 5 of 9 title queries before one
    fails) so a mid-run failure doesn't discard good results."""

    def __init__(self, message: str, partial_results: list[dict] | None = None):
        super().__init__(message)
        self.partial_results = partial_results or []
