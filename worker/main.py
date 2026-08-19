import logging
import os
import sys
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

logger = logging.getLogger(__name__)


def main() -> None:
    import django
    django.setup()

    from worker.ws.extension_ws_server import start_extension_ws_server

    logger.info("Sentinel worker starting up")

    extension_ws_thread = threading.Thread(
        target=start_extension_ws_server,
        name="ExtensionWebSocketServer",
        daemon=True,
    )
    extension_ws_thread.start()
    logger.info("Extension WebSocket server thread started")

    logger.info("Sentinel worker ready")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Sentinel worker shutting down")


if __name__ == "__main__":
    main()
