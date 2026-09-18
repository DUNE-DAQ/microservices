"""Health check HTTP server for Kubernetes probes."""

import logging
from http import HTTPStatus
from threading import Thread
from typing import Callable

from flask import Flask, jsonify
from werkzeug.serving import make_server

logger = logging.getLogger(__name__)


class HealthServer:
    """Provides HTTP health check endpoints for Kubernetes probes.

    Serves /live (liveness) and /ready (readiness) endpoints on a background thread.
    """

    def __init__(self, port: int, health_check: Callable[[], bool]) -> None:
        """Initialize health server.

        Args:
            port: Port to listen on.
            health_check: Callable that returns True if system is healthy.
        """
        self._health_check = health_check
        self.port = port
        self.app = Flask(__name__)

        self._register_routes(self.app)
        self._server = make_server("0.0.0.0", port, self.app)  # noqa: S104
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    def _register_routes(self, app: Flask) -> None:
        """Register Flask routes for health checks.

        Args:
            app: Flask application instance.
        """

        @app.get("/ready")
        def ready() -> tuple[dict, int]:
            """Readiness probe endpoint.

            Returns 200 OK if healthy (DB connected), 503 SERVICE_UNAVAILABLE if not ready.
            """
            logger.debug("Readiness probe received")
            healthy = self._health_check()
            status = HTTPStatus.OK if healthy else HTTPStatus.SERVICE_UNAVAILABLE
            return (
                jsonify(
                    status="ready" if healthy else "not ready",
                    timescaledb="healthy" if healthy else "unreachable",
                ),
                status.value,
            )

        @app.get("/live")
        def live() -> tuple[dict, int]:
            """Liveness probe endpoint.

            Always returns 200 OK if this endpoint is reachable.
            """
            logger.debug("Liveness probe received")
            return jsonify(status="live"), HTTPStatus.OK.value

    def start(self) -> None:
        """Start health server on background daemon thread."""
        logger.info("Health server started on port %d", self.port)
        self._thread.start()

    def stop(self) -> None:
        """Shutdown health server."""
        logger.info("Shutting down health server")
        self._server.shutdown()
