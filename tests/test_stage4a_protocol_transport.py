import json
import threading
import unittest
from unittest.mock import patch

import numpy as np
from websockets.sync.server import serve

from reachy_stage4.runtime import ReachySdkAdapter
from reachy_stage4.safety import target_point


class Stage4AProtocolTransportTests(unittest.TestCase):
    def test_official_task_schema_is_head_only_and_bounded(self):
        requests = []

        def handler(socket):
            socket.send(json.dumps({
                "type": "daemon_status",
                "robot_name": "reachy_mini",
                "state": "running",
                "simulation_enabled": False,
                "mockup_sim_enabled": False,
                "version": "1.9.0",
                "error": None,
                "backend_status": {
                    "ready": False,
                    "motor_control_mode": "enabled",
                    "error": None,
                    "control_loop_stats": {
                        "mean_control_loop_frequency": 50.0,
                        "max_control_loop_interval": 0.02,
                        "nb_error": 0,
                        "motor_controller": "healthy",
                    },
                },
            }))
            socket.send(json.dumps({"type": "head_pose", "head_pose": np.eye(4).tolist()}))
            raw = socket.recv(timeout=5.0)
            request = json.loads(raw)
            requests.append(request)
            target = np.asarray(request["req"]["head"]).reshape(4, 4)
            socket.send(json.dumps({"type": "head_pose", "head_pose": target.tolist()}))
            socket.send(json.dumps({
                "type": "task_progress",
                "uuid": request["uuid"],
                "finished": True,
                "error": None,
                "timestamp": "2026-08-31T18:00:00+00:00",
            }))

        server = serve(handler, "127.0.0.1", 0)
        port = server.socket.getsockname()[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch("reachy_stage4.runtime.REACHY_PORT", port):
                adapter = ReachySdkAdapter("127.0.0.1")
                self.assertFalse(adapter.status()["backend_ready"])
                self.assertLess(adapter.status()["head_pose_age_s"], 2.0)
                target = adapter.target_pose(target_point("UP"))
                adapter.goto_head_only(target, 0.1)
                np.testing.assert_allclose(adapter.current_pose(), target)
                adapter.disconnect()
        finally:
            server.shutdown()
            thread.join(timeout=5.0)

        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request["type"], "task")
        self.assertEqual(request["req"]["method"], "minjerk")
        self.assertIsNone(request["req"]["body_yaw"])
        self.assertIsNone(request["req"]["antennas"])
        self.assertEqual(len(request["req"]["head"]), 16)
        self.assertNotIn("torque", json.dumps(request).lower())
        self.assertNotIn("motor", json.dumps(request).lower())


if __name__ == "__main__":
    unittest.main()
