import asyncio
import json
import logging
import os

import websockets

logger  = logging.getLogger(__name__)
WS_PORT = int(os.environ.get('EXTENSION_WS_PORT', 8140))


def _log_page_structure(payload: dict) -> None:
    frames = payload.get('frames', [])
    logger.info('page_structure: %d frame(s) from tab %s', len(frames), payload.get('tab_id'))
    for frame in frames:
        summary = frame.get('summary') or {}
        logger.info(
            '  frame %s %s — forms=%d loose_fields=%d buttons=%d links=%d',
            frame.get('frameId'), summary.get('url'),
            len(summary.get('forms', [])),
            len(summary.get('loose_fields', [])),
            len(summary.get('buttons', [])),
            len(summary.get('links', [])),
        )


async def _handle(websocket) -> None:
    logger.info('Extension WS connected: %s', websocket.remote_address)

    try:
        async for raw in websocket:
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {'raw': raw}

            if payload.get('type') == 'page_structure':
                _log_page_structure(payload)

            await websocket.send(json.dumps({'type': 'echo', 'received': payload}))

    except websockets.ConnectionClosed:
        pass

    logger.info('Extension WS disconnected: %s', websocket.remote_address)


async def _serve() -> None:
    async with websockets.serve(_handle, '0.0.0.0', WS_PORT):
        logger.info('Extension WebSocket server listening on port %d', WS_PORT)
        await asyncio.Future()


def start_extension_ws_server() -> None:
    asyncio.run(_serve())
