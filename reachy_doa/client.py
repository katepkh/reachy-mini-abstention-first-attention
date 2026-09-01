"""The only module allowed to communicate with Reachy Mini."""

from __future__ import annotations

import ipaddress
import math
import time
from datetime import datetime, timezone

import requests

from .config import (
    ALLOWED_PATH,
    ALLOWED_PORT,
    ALLOWED_SCHEME,
    REQUEST_TIMEOUT_SECONDS,
)
from .models import DoAReading


class EndpointRejected(ValueError):
    """Raised when an address cannot be reduced to the read-only allowlist."""


class ReadOnlyDoAClient:
    """Fetch DoA snapshots from exactly one allowlisted local endpoint."""

    def __init__(self, robot_ip: str, timeout: float = REQUEST_TIMEOUT_SECONDS) -> None:
        address = ipaddress.ip_address(robot_ip.strip())
        if address.version != 4 or not (address.is_private or address.is_loopback):
            raise EndpointRejected("Use a private IPv4 address from Reachy Mini Control.")
        self.robot_ip = str(address)
        self.timeout = min(max(float(timeout), 0.2), REQUEST_TIMEOUT_SECONDS)
        self.allowed_endpoint = (
            f"{ALLOWED_SCHEME}://{self.robot_ip}:{ALLOWED_PORT}{ALLOWED_PATH}"
        )
        # Reuse one local HTTP connection for the lifetime of this client.
        # This avoids opening a new TCP connection for every 5 Hz observation.
        session = requests.Session()
        session.trust_env = False
        self._session = session

    def read(self) -> DoAReading:
        """Read one snapshot. This class exposes no mutating network operation."""
        started = time.perf_counter()
        captured = datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")
        status: int | None = None
        try:
            session = self._session
            response = session.get(
                self.allowed_endpoint,
                timeout=self.timeout,
                allow_redirects=False,
            )
            status = response.status_code
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("The endpoint returned no DoA object.")

            angle = payload.get("angle")
            speech = payload.get("speech_detected")
            if isinstance(angle, bool) or not isinstance(angle, (int, float)):
                raise ValueError("The response did not contain a numeric angle.")
            if not math.isfinite(float(angle)):
                raise ValueError("The response angle was not finite.")
            if not isinstance(speech, bool):
                raise ValueError("The response did not contain a speech flag.")

            return DoAReading(
                client_time_iso=captured,
                captured_monotonic=time.perf_counter(),
                raw_angle_rad=float(angle),
                speech_detected=speech,
                http_latency_ms=(time.perf_counter() - started) * 1000.0,
                http_status=status,
                valid=True,
                error="",
            )
        except (requests.RequestException, ValueError) as exc:
            return DoAReading(
                client_time_iso=captured,
                captured_monotonic=time.perf_counter(),
                raw_angle_rad=None,
                speech_detected=None,
                http_latency_ms=(time.perf_counter() - started) * 1000.0,
                http_status=status,
                valid=False,
                error=str(exc)[:240],
            )

    def close(self) -> None:
        """Close the laptop-side connection pool; no robot request is sent."""
        self._session.close()
