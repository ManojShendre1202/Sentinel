"""
Extension-driven counterpart to test_navigate_shortlist.py (which used
Playwright). Same idea — pick a real shortlisted job's URL from the DB,
drive the application flow step by step with Gemini — but this time
through the real Chrome extension (capture_page / action over the
worker's WebSocket) instead of a Playwright-controlled browser.

Requires:
  - nginx up on 8100 (proxies /ws/extension/ to the worker WS server)
  - the real worker (worker/main.py) NOT running, since this command binds
    port 8140 itself to stand in for it — same approach as
    scripts/test_extension_ws.py
  - the Sentinel extension loaded in your normal Chrome profile, connected
  - Chrome's ACTIVE tab pointed at the printed URL before each step

Usage:
    python manage.py test_navigate_shortlist_extension
    python manage.py test_navigate_shortlist_extension --job-id 42
"""
import asyncio
import json
import os

import websockets
from django.core.management.base import BaseCommand
from google.genai import errors as genai_errors

from backend.core.models import Shortlist
from backend.graphs.nodes.decide_next_action import decide

GOAL = "Complete and submit the job application on this page, step by step."
WS_PORT = int(os.environ.get("EXTENSION_WS_PORT", 8140))
DEBUG_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "debug_capture.log")


class Command(BaseCommand):
    help = "Pick a real shortlisted job's URL from the DB and drive its application flow through the Chrome extension."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int, default=None, help="JobListing pk to use. Defaults to the highest-scored 'shortlisted' row.")

    def handle(self, *args, **options):
        shortlist_qs = Shortlist.objects.select_related("job")
        if options["job_id"]:
            shortlist = shortlist_qs.filter(job_id=options["job_id"]).first()
        else:
            shortlist = shortlist_qs.order_by("-match_score").first()

        if not shortlist:
            self.stdout.write(self.style.ERROR("No Shortlist row found at all. Pass --job-id or run Graph 1 first."))
            return

        job = shortlist.job
        self.stdout.write(f"Job: {job.title} @ {job.company} (status={shortlist.status}, match_score={shortlist.match_score})")
        self.stdout.write(f"URL: {job.url}")
        self.stdout.write("")

        asyncio.run(self._run(job.url))

    async def _run(self, url: str) -> None:
        history: list[str] = []
        navigated = False
        step = 0

        with open(DEBUG_LOG_PATH, "w", encoding="utf-8") as f:
            f.write("")  # reset log at the start of each run

        async def recv_msg(websocket):
            """recv() that silently discards unsolicited keepalive_ping frames
            from the extension's chrome.alarms heartbeat, so they can't be
            mistaken for the response to whatever we just sent."""
            while True:
                raw = await websocket.recv()
                msg = json.loads(raw)
                if msg.get("type") == "keepalive_ping":
                    continue
                return msg

        async def handler(websocket):
            self.stdout.write(self.style.SUCCESS(f"Extension connected: {websocket.remote_address}"))
            try:
                # Drain the initial "hello".
                await asyncio.wait_for(websocket.recv(), timeout=5)
            except asyncio.TimeoutError:
                pass

            nonlocal navigated
            if not navigated:
                navigated = True  # claim before awaiting anything, so a concurrent handler can't slip through
                self.stdout.write(f"Navigating extension to: {url}")
                await websocket.send(json.dumps({"type": "navigate", "task_id": "nav_open", "url": url}))
                nav_result = await recv_msg(websocket)
                if nav_result.get("type") != "navigated":
                    self.stdout.write(self.style.ERROR(f"navigate failed: {nav_result}"))
                    navigated = False
                    return
            else:
                self.stdout.write("Reconnected — reusing existing tab, not opening a new one.")

            while True:
                await websocket.send(json.dumps({"type": "capture_page", "task_id": "nav_step"}))
                msg = await recv_msg(websocket)

                if msg.get("type") == "capture_error":
                    self.stdout.write(self.style.ERROR(f"capture_page failed: {msg.get('error')}"))
                    break

                frames = msg.get("frames", [])
                if not frames:
                    self.stdout.write(self.style.ERROR("No frames captured."))
                    break

                # Use the top-level (frameId 0) frame's summary for the decision.
                top = next((f for f in frames if f.get("frameId") == 0), frames[0])
                summary = top.get("summary") or {}
                current_url = summary.get("url", url)

                nonlocal step
                step += 1
                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(f"\n===== STEP {step} =====\n")
                    f.write(f"used_frame_id: {top.get('frameId')}\n")
                    f.write(f"all_frames_captured (raw, includes what's NOT sent to Gemini):\n")
                    f.write(json.dumps(frames, indent=2))
                    f.write("\n\nsummary_sent_to_gemini:\n")
                    f.write(json.dumps(summary, indent=2))
                    f.write("\n")

                self.stdout.write(f"\ncurrent_url: {current_url}")
                self.stdout.write(
                    f"forms={len(summary.get('forms', []))} "
                    f"loose_fields={len(summary.get('loose_fields', []))} "
                    f"buttons={len(summary.get('buttons', []))} "
                    f"links={len(summary.get('links', []))}"
                )

                try:
                    decision = decide(GOAL, summary, current_url=current_url, history=history)
                except genai_errors.ClientError as exc:
                    self.stdout.write(self.style.ERROR(f"Gemini call failed, stopping: {exc}"))
                    break
                self.stdout.write(f"page_state: {decision['page_state']}")
                self.stdout.write(f"reasoning: {decision['reasoning']}")
                self.stdout.write(f"action: {decision['action']}")

                with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write("\ndecision:\n")
                    f.write(json.dumps(decision, indent=2))
                    f.write("\n")

                if decision["page_state"] in ("captcha_present", "confirmation_page"):
                    self.stdout.write(self.style.WARNING(f"Stopping — page_state={decision['page_state']}"))
                    break

                answer = input("Run this action? [y/N/q to stop] ").strip().lower()
                if answer == "q":
                    break
                if answer != "y":
                    continue

                action = decision["action"]
                await websocket.send(json.dumps({
                    "type": "action",
                    "task_id": "nav_step",
                    "frame_id": top.get("frameId", 0),
                    "action": action,
                }))
                result = await recv_msg(websocket)
                self.stdout.write(f"action_result: {result}")

                history.append(f"{action.get('type')}: {action.get('target')}")

                if input("Continue to next step? [Y/n] ").strip().lower() == "n":
                    break

            self.stdout.write("Done. Ctrl+C to exit.")

        async with websockets.serve(handler, "0.0.0.0", WS_PORT):
            self.stdout.write(self.style.SUCCESS(f"Listening on port {WS_PORT} — waiting for extension to (re)connect..."))
            await asyncio.Future()
