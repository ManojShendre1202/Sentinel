"""
Standalone smoke test for the extension <-> worker WebSocket link.

Stands in for worker/ws/extension_ws_server.py so it can drive the
extension directly and print results — run this INSTEAD of the real worker
(stop worker/main.py first), keep nginx running. The extension auto-
reconnects, so once this script is listening on 8140, the extension's
existing connection to ws://localhost:8100/ws/extension/ picks it up
within a few seconds (its reconnect backoff).

Usage:
    python scripts/test_extension_ws.py

Steps once the extension connects:
  1. Wait for "hello" from the extension.
  2. Send capture_page and print the returned DOM summary per frame
     (forms/loose_fields/buttons/links counts + titles/urls) — this is the
     same data the popup's "Last capture" pane renders.
  3. Send one small, harmless action (click a "test" no-op target) and
     print the action_result — confirms the action round-trip works even
     though nothing on a real page will match this target.
"""
import asyncio
import json
import logging
import os

import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_extension_ws")

WS_PORT = int(os.environ.get("EXTENSION_WS_PORT", 8140))


async def _run_test(websocket) -> None:
    logger.info("Extension connected: %s", websocket.remote_address)

    async def send_and_wait(payload, expect_types, timeout=10):
        await websocket.send(json.dumps(payload))
        logger.info("-> sent %s", payload)
        while True:
            raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
            msg = json.loads(raw)
            logger.info("<- received %s", json.dumps(msg)[:500])
            if msg.get("type") in expect_types:
                return msg

    # Step 1: wait for hello (in case it hasn't arrived yet)
    try:
        hello = await asyncio.wait_for(websocket.recv(), timeout=5)
        logger.info("<- initial message %s", hello)
    except asyncio.TimeoutError:
        logger.info("(no initial message within 5s, continuing anyway)")

    # Step 2: capture_page
    capture = await send_and_wait(
        {"type": "capture_page", "task_id": "smoke_test_capture"},
        expect_types={"page_structure", "capture_error"},
    )
    if capture.get("type") == "capture_error":
        logger.error("capture_page FAILED: %s", capture.get("error"))
    else:
        frames = capture.get("frames", [])
        logger.info("capture_page OK — %d frame(s)", len(frames))
        for f in frames:
            s = f.get("summary") or {}
            logger.info(
                "  frame %s | %s | title=%r forms=%d loose_fields=%d buttons=%d links=%d",
                f.get("frameId"), s.get("url"), s.get("title"),
                len(s.get("forms", [])), len(s.get("loose_fields", [])),
                len(s.get("buttons", [])), len(s.get("links", [])),
            )

    # Step 3: a small harmless action
    action_result = await send_and_wait(
        {
            "type": "action",
            "task_id": "smoke_test_action",
            "frame_id": 0,
            "action": {"type": "wait", "target": ""},
        },
        expect_types={"action_result", "action_error"},
    )
    logger.info("action round-trip: %s", action_result)

    logger.info("Smoke test complete. Leaving connection open — Ctrl+C to stop.")

    # Keep the connection alive so you can manually trigger the popup's
    # "Capture active tab" / "Send test ping" buttons and watch them logged.
    async for raw in websocket:
        try:
            msg = json.loads(raw)
        except Exception:
            msg = {"raw": raw}
        logger.info("<- (post-test) %s", json.dumps(msg)[:500])


async def _serve() -> None:
    async with websockets.serve(_run_test, "0.0.0.0", WS_PORT):
        logger.info("Test WS server listening on port %d — reload the extension or wait for its reconnect", WS_PORT)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(_serve())
