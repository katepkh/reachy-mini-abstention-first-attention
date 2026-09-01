"""Local-LAN, receive-only WebRTC consumer for Reachy Mini video.

The signalling flow is adapted from Pollen Robotics' Apache-2.0 licensed
Home Assistant integration. It talks directly to the robot's built-in
GStreamer signalling service and has no STUN, TURN, cloud, authentication,
data-channel or robot-controller path.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import ipaddress
import json
import time
from collections.abc import Callable
from typing import Any

from .config import (
    CAMERA_PROXY_HOST,
    MAX_CAMERA_RUNTIME_SECONDS,
    OUTBOUND_MESSAGE_TYPES,
    PRODUCER_NAME,
    SIGNALLING_PORT,
    SIGNALLING_SCHEME,
    VIDEO_FRAME_TIMEOUT_SECONDS,
    VIDEO_STARTUP_GRACE_SECONDS,
    VIDEO_STARTUP_FRAME_TIMEOUT_SECONDS,
)


class LocalStreamRejected(ValueError):
    """Raised when camera signalling is not an exact private-LAN target."""


class LocalStreamUnavailable(RuntimeError):
    """Raised when Reachy's local video producer cannot be acquired."""


def camera_connector_error_code(exc: BaseException) -> str:
    """Distinguish an unavailable bridge from an OS-denied socket.

    Windows reports a sandbox/firewall denial as WinError 10013.  Treating
    every aiohttp connector error as an unavailable camera proxy hid the
    execution-permission problem and sent the dashboard into futile reconnect
    loops.  This helper is intentionally transport-only and contains no retry.
    """
    os_error = getattr(exc, "os_error", None)
    winerror = getattr(os_error, "winerror", None)
    error_number = getattr(os_error, "errno", None)
    if winerror == 10013 or error_number in {errno.EACCES, errno.EPERM}:
        return "CAMERA_NETWORK_ACCESS_DENIED"
    return "CAMERA_PROXY_UNAVAILABLE"


def local_signalling_url(camera_host: str = CAMERA_PROXY_HOST) -> str:
    """Return an allowlisted loopback or private-LAN camera endpoint."""
    address = ipaddress.ip_address(camera_host.strip())
    if address.version != 4 or not (address.is_private or address.is_loopback):
        raise LocalStreamRejected(
            "Use Reachy's private IPv4 address or the localhost camera proxy."
        )
    return f"{SIGNALLING_SCHEME}://{address}:{SIGNALLING_PORT}"


async def _send_allowed(ws: Any, message: dict[str, Any]) -> None:
    message_type = message.get("type")
    if message_type not in OUTBOUND_MESSAGE_TYPES:
        raise LocalStreamRejected("Outbound signalling message is not allowlisted.")
    await ws.send_json(message)


def _peer_connection() -> Any:
    """Create an aiortc receiver with no external ICE servers.

    Reachy's GStreamer DTLS certificate uses RSA. The small private-attribute
    interop shim matches Pollen's tested local consumer and is pinned by tests.
    """
    from aiortc import RTCConfiguration, RTCPeerConnection
    from aiortc.rtcdtlstransport import RTCCertificate
    from OpenSSL import SSL

    class InteropCertificate(RTCCertificate):
        def _create_ssl_context(self, srtp_profiles: list[Any]) -> Any:
            context = super()._create_ssl_context(srtp_profiles)
            context.set_cipher_list(
                b"ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384"
            )
            return context

        @classmethod
        def generate(cls) -> Any:
            base = RTCCertificate.generateCertificate()
            return cls(key=base._key, cert=base._cert)

    connection = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    connection._RTCPeerConnection__certificates = [InteropCertificate.generate()]
    return connection


class LocalVideoSession:
    """One bounded, receive-only local camera session."""

    def __init__(
        self,
        *,
        detection_hz: float = 5.0,
        max_runtime_seconds: float = MAX_CAMERA_RUNTIME_SECONDS,
        signalling_host: str = CAMERA_PROXY_HOST,
    ) -> None:
        self.signalling_url = local_signalling_url(signalling_host)
        self.detection_period = 1.0 / min(10.0, max(1.0, float(detection_hz)))
        self.max_runtime_seconds = min(
            MAX_CAMERA_RUNTIME_SECONDS,
            max(10.0, float(max_runtime_seconds)),
        )
        self._session_id: str | None = None
        self._video_task: asyncio.Task[Any] | None = None

    async def run(
        self,
        stop_requested: Callable[[], bool],
        on_frame: Callable[[Any], None],
        on_status: Callable[[str, str], None],
        on_transport_frame: Callable[[float], None] | None = None,
    ) -> None:
        import aiohttp

        started = time.monotonic()
        on_status("CONNECTING", "")
        async with aiohttp.ClientSession(trust_env=False) as session:
            task = asyncio.create_task(
                self._run_session(session, on_frame, on_status, on_transport_frame)
            )
            try:
                while not task.done():
                    if stop_requested():
                        on_status("STOPPING", "")
                        break
                    if time.monotonic() - started >= self.max_runtime_seconds:
                        on_status("AUTO_STOPPING", "MAX_RUNTIME_REACHED")
                        break
                    await asyncio.sleep(0.1)
            finally:
                if not task.done():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _run_session(
        self,
        session: Any,
        on_frame: Callable[[Any], None],
        on_status: Callable[[str, str], None],
        on_transport_frame: Callable[[float], None] | None,
    ) -> None:
        import aiohttp
        from aiortc import RTCSessionDescription
        from aiortc.sdp import candidate_from_sdp

        connection = _peer_connection()
        self._session_id = None
        terminal_error = ""
        try:
            async with session.ws_connect(self.signalling_url, heartbeat=20) as ws:
                connection.on(
                    "track",
                    lambda track: self._on_track(
                        track, on_frame, on_status, on_transport_frame
                    ),
                )
                async for raw in ws:
                    if raw.type != aiohttp.WSMsgType.TEXT:
                        break
                    message = json.loads(raw.data)
                    message_type = message.get("type")
                    if message_type == "welcome":
                        await _send_allowed(ws, {"type": "list"})
                    elif message_type == "list":
                        producer_id = next(
                            (
                                producer.get("id")
                                for producer in message.get("producers", [])
                                if producer.get("meta", {}).get("name") == PRODUCER_NAME
                            ),
                            None,
                        )
                        if not producer_id:
                            raise LocalStreamUnavailable("VIDEO_PRODUCER_NOT_AVAILABLE")
                        await _send_allowed(
                            ws,
                            {"type": "startSession", "peerId": producer_id},
                        )
                    elif message_type == "sessionStarted":
                        self._session_id = str(message["sessionId"])
                    elif message_type == "peer" and "sdp" in message:
                        offer = message["sdp"]
                        await connection.setRemoteDescription(
                            RTCSessionDescription(offer["sdp"], offer["type"])
                        )
                        await connection.setLocalDescription(await connection.createAnswer())
                        answer_sdp = connection.localDescription.sdp
                        await _send_allowed(
                            ws,
                            {
                                "type": "peer",
                                "sessionId": self._session_id,
                                "sdp": {"type": "answer", "sdp": answer_sdp},
                            },
                        )
                        media_line = -1
                        for line in answer_sdp.splitlines():
                            if line.startswith("m="):
                                media_line += 1
                            elif line.startswith("a=candidate:"):
                                await _send_allowed(
                                    ws,
                                    {
                                        "type": "peer",
                                        "sessionId": self._session_id,
                                        "ice": {
                                            "candidate": line[2:],
                                            "sdpMLineIndex": media_line,
                                        },
                                    },
                                )
                    elif message_type == "peer" and "ice" in message:
                        ice = message["ice"] or {}
                        candidate_text = ice.get("candidate")
                        if candidate_text:
                            candidate = candidate_from_sdp(
                                candidate_text.replace("candidate:", "", 1)
                            )
                            candidate.sdpMLineIndex = ice.get("sdpMLineIndex", 0)
                            await connection.addIceCandidate(candidate)
                    elif message_type == "endSession":
                        break
        except asyncio.CancelledError:
            raise
        except aiohttp.ClientConnectorError as exc:
            terminal_error = camera_connector_error_code(exc)
            on_status("ERROR", terminal_error)
        except Exception as exc:
            terminal_error = type(exc).__name__.upper()[:64]
            on_status("ERROR", terminal_error)
        finally:
            if self._session_id is not None and "ws" in locals() and not ws.closed:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(
                        _send_allowed(
                            ws,
                            {"type": "endSession", "sessionId": self._session_id},
                        ),
                        timeout=1.0,
                    )
            if self._video_task is not None:
                self._video_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await self._video_task
                self._video_task = None
            with contextlib.suppress(Exception):
                await connection.close()
            if not terminal_error:
                on_status("STOPPED", "")

    def _on_track(
        self,
        track: Any,
        on_frame: Callable[[Any], None],
        on_status: Callable[[str, str], None],
        on_transport_frame: Callable[[float], None] | None,
    ) -> None:
        if track.kind == "video" and self._video_task is None:
            on_status("RECEIVING", "")
            self._video_task = asyncio.get_running_loop().create_task(
                self._consume_video(track, on_frame, on_status, on_transport_frame)
            )

    async def _consume_video(
        self,
        track: Any,
        on_frame: Callable[[Any], None],
        on_status: Callable[[str, str], None],
        on_transport_frame: Callable[[float], None] | None = None,
    ) -> None:
        from aiortc.mediastreams import MediaStreamError

        next_detection = 0.0
        detection_task: asyncio.Task[None] | None = None
        loop = asyncio.get_running_loop()
        track_started = loop.time()

        async def detect_owned(pixels: Any) -> None:
            """Run one detector call without blocking WebRTC frame draining."""
            try:
                await asyncio.to_thread(on_frame, pixels)
            finally:
                # Pixel arrays are intentionally short-lived and never leave
                # this receive-only transport boundary.
                del pixels

        try:
            while True:
                startup = loop.time() - track_started < VIDEO_STARTUP_GRACE_SECONDS
                frame_timeout = (
                    VIDEO_STARTUP_FRAME_TIMEOUT_SECONDS
                    if startup
                    else VIDEO_FRAME_TIMEOUT_SECONDS
                )
                frame = await asyncio.wait_for(
                    track.recv(), timeout=frame_timeout
                )
                now = loop.time()
                if on_transport_frame is not None:
                    on_transport_frame(time.perf_counter())
                if now < next_detection:
                    continue
                # Face analysis can occasionally take longer than its nominal
                # period under Streamlit/Windows load. Awaiting it here used
                # to stop us draining WebRTC, causing healthy video to be
                # reported as stale. Keep at most one analysis in flight and
                # drop analysis samples (never transport frames) while busy.
                if detection_task is not None:
                    if not detection_task.done():
                        continue
                    await detection_task
                next_detection = now + self.detection_period
                pixels = frame.to_ndarray(format="bgr24")
                detection_task = asyncio.create_task(detect_owned(pixels))
        except TimeoutError:
            # A negotiated track can remain open after its source stops
            # producing frames.  Report that transport failure explicitly so
            # the dashboard never mistakes a frozen frame for a face problem.
            error_code = (
                "VIDEO_STARTUP_FRAME_TIMEOUT"
                if loop.time() - track_started < VIDEO_STARTUP_GRACE_SECONDS
                else "VIDEO_FRAME_TIMEOUT"
            )
            on_status("ERROR", error_code)
            return
        except MediaStreamError:
            # Do not leave the worker marked RECEIVING with a frozen final
            # observation after Reachy's video track ends. The dashboard can
            # now fail closed and perform one bounded local reconnect.
            on_status("ERROR", "VIDEO_TRACK_ENDED")
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            on_status("ERROR", f"VIDEO_TRACK_{type(exc).__name__.upper()}"[:64])
            return
        finally:
            if detection_task is not None:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await detection_task
