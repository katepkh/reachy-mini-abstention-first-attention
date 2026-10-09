"""Small fixed HTTP worker pool; no per-request thread or unbounded backlog."""

from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer


class BoundedHTTPServer(HTTPServer):
    """Two reusable workers, at most six admitted sockets, and bounded socket IO.

    A slow sensor GET can occupy one worker without blocking the frame route.
    Overload closes the excess connection instead of growing an executor queue.
    This is a loopback development server, not an internet-facing web server.
    """

    worker_count = 2
    pending_capacity = 4
    request_queue_size = 6
    socket_timeout_seconds = 2.0

    def __init__(self, *args, **kwargs):
        self._pool = None
        self._closing = False
        self._pending_lock = threading.Lock()
        self._pending: set[socket.socket] = set()
        self._slots = threading.BoundedSemaphore(self.worker_count + self.pending_capacity)
        self._request_context = threading.local()
        super().__init__(*args, **kwargs)
        self._pool = ThreadPoolExecutor(
            max_workers=self.worker_count, thread_name_prefix="camera-http"
        )

    @property
    def request_queue_wait_ms(self) -> float:
        # Accept-to-worker only; excludes the OS accept backlog/browser queue.
        return getattr(self._request_context, "queue_wait_ms", 0.0)

    def process_request(self, request, client_address):
        accepted = time.perf_counter()
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            request.settimeout(self.socket_timeout_seconds)
            with self._pending_lock:
                if self._closing:
                    self.shutdown_request(request)
                    self._slots.release()
                    return
                self._pending.add(request)
                self._pool.submit(self._serve_request, request, client_address, accepted)
        except Exception:
            with self._pending_lock:
                self._pending.discard(request)
            self._slots.release()
            self.shutdown_request(request)
            raise

    def _serve_request(self, request, client_address, accepted):
        self._request_context.queue_wait_ms = 1000.0 * (time.perf_counter() - accepted)
        try:
            if not self._closing:
                self.finish_request(request, client_address)
        except OSError:
            # Browser cancellation, socket timeout, or deliberate shutdown.
            pass
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)
            with self._pending_lock:
                self._pending.discard(request)
            self._slots.release()

    def server_close(self):
        super().server_close()
        with self._pending_lock:
            self._closing = True
            pending = list(self._pending)
        # Signal incomplete HTTP reads/writes before joining the fixed workers.
        # Windows may finish at the existing two-second socket IO timeout.
        # In-flight DoA uses its existing bounded robot HTTP timeout.
        for request in pending:
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self._pool is not None:
            self._pool.shutdown(wait=True)
