import logging
from threading import Thread
from typing import Callable

from flask import Flask, jsonify
from werkzeug.serving import make_server

logger = logging.getLogger(__name__)


class HealthServer:
    def __init__(self, port: int, health_check: Callable[[], bool]):
        self._health_check = health_check
        self.port = port
        self.app = Flask(__name__)
        
        self._register_routes(self.app)
        self._server = make_server("0.0.0.0", port, self.app)  # noqa: S104
        self._thread = Thread(target=self._server.serve_forever, daemon=True)


    def _register_routes(self, app: Flask) -> None:
        @app.get("/ready")
        def ready():
            healthy = self._health_check()
            status = 200 if healthy else 503
            return jsonify(
                status="ready" if healthy else "not ready",
                timescaledb="healthy" if healthy else "unreachable",
            ), status

        @app.get("/live")
        def live():
            return jsonify(status="live"), 200

    def start(self) -> None:
        logger.info("Health server started on port %d", self.port)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
