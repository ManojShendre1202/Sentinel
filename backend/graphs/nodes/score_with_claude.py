"""
Graph 1, node 4 — score_with_claude.

Invokes `claude -p` (headless CLI, runs against the existing Claude
subscription's included usage, not metered API billing) against batch.json,
instructed to read profile.md and write results.json per the rubric below.

Rubric (per job, each dimension 0-10):
- skills_fit: required/nice-to-have skills match against profile's
  Experience/Skills sections
- seniority_fit: JD's experience ask vs profile's ~2 years (May 2024-present)
- location_fit: Bangalore/remote favored highest; other India cities lower;
  non-remote outside Bangalore lowest (profile: Bangalore-primary, not open
  to relocation, remote acceptable)
- company_fit: profile's target company tiers favored; staffing/outsourcing
  agencies and tiny/early-stage startups penalized
- ctc_fit: null if no salary data in `signals` (not penalized for missing
  data), else scored against profile's CTC floor/ask

`status` (shortlisted/rejected) is Claude's holistic call, not a rigid
score threshold — dimension scores + reasoning exist for audit, not to be
mechanically summed.
"""
import shutil
import subprocess
from pathlib import Path

RESULTS_PATH = Path(__file__).resolve().parent.parent / "batch_data" / "results.json"

PROMPT_TEMPLATE = """\
This is a one-shot, non-interactive run — there is no follow-up turn. Do \
not summarize, ask clarifying questions, or wait for confirmation. Score \
every job and write the results file yourself, now, in this run.

Read the batch file at {batch_json_path}. It has "profile_path" (read that \
file for the candidate's background/skills/preferences) and "jobs" (a list \
of job postings to score).

For each job, score these dimensions 0-10:
- skills_fit: required/nice-to-have skills match against the profile's Experience/Skills sections
- seniority_fit: this job's experience ask vs the candidate's ~2 years experience
- location_fit: Bangalore or remote = highest; other India cities = lower; non-remote outside Bangalore = lowest (candidate is Bangalore-primary, not open to relocation, remote acceptable)
- company_fit: candidate's target company tiers favored; staffing/outsourcing agencies and tiny/early-stage startups penalized
- ctc_fit: null if the job's `signals` has no salary data (do not penalize missing data), else score against the candidate's CTC floor/ask from the profile

Then give an overall match_score (0-10, your holistic judgment, not a \
mechanical average of the dimensions), a status of either "shortlisted" or \
"rejected", and a short reasoning string (2-4 sentences, cite specific \
evidence from the job description and profile).

Write your output to {results_json_path} as JSON in exactly this shape:
{{
  "results": [
    {{
      "job_listing_id": <int, copied from the input job>,
      "status": "shortlisted" | "rejected",
      "match_score": <float 0-10>,
      "dimension_scores": {{"skills_fit": <float>, "seniority_fit": <float>, "location_fit": <float>, "company_fit": <float>, "ctc_fit": <float or null>}},
      "reasoning": "<string>"
    }}
  ]
}}

Include exactly one result per job in the input batch, in any order. Write \
only the JSON file — no other output.
"""


def score_batch(batch_json_path: str) -> str:
    prompt = PROMPT_TEMPLATE.format(batch_json_path=batch_json_path, results_json_path=str(RESULTS_PATH))

    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise RuntimeError("claude CLI not found on PATH")

    # BUG GUARD: score_batch() previously only checked RESULTS_PATH.exists(),
    # which silently "succeeded" against a stale results.json left over from
    # a prior run when claude -p failed to write a fresh one. Delete any
    # leftover file first so existence alone can't be mistaken for success.
    RESULTS_PATH.unlink(missing_ok=True)

    # This runs unattended (cron / management command) with no TTY to answer
    # a permission prompt, so --allowed-tools alone isn't enough — some
    # underlying confirmations (dir access, write confirmation) still fire
    # and hang forever with no one to answer them. Scoped safely here: this
    # call only ever reads batch_json_path/profile.md and writes to the
    # fixed RESULTS_PATH under graphs/batch_data/, never arbitrary paths.
    #
    # Prompt is piped via stdin, NOT passed as a CLI argument: on Windows,
    # `claude` resolves to a .cmd batch shim (`%*` arg forwarding), and
    # cmd.exe's argument parsing breaks on embedded newlines within a single
    # argument — our multi-line PROMPT_TEMPLATE was silently corrupting/
    # dropping every flag that came after it (--dangerously-skip-permissions,
    # --allowedTools), which is why the write kept getting blocked no matter
    # what flags were added. Piping via stdin avoids the shim entirely.
    result = subprocess.run(
        [
            claude_bin, "-p",
            "--dangerously-skip-permissions",
            "--allowedTools", "Write,Edit,Bash,Read,Create",
        ],
        input=prompt,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode})")

    if not RESULTS_PATH.exists():
        raise RuntimeError("claude -p did not write results.json")

    return str(RESULTS_PATH)
