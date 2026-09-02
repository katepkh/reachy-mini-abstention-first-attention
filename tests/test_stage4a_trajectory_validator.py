import ast
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_successor_trajectory_v190.py"


class TrajectoryValidatorTests(unittest.TestCase):
    def test_validator_has_no_network_or_command_calls(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(
            imports.isdisjoint({"requests", "httpx", "aiohttp", "websockets", "socket"})
        )
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(
            called.isdisjoint({"send", "connect", "post", "put", "patch", "delete", "goto_target", "set_target"})
        )

    def test_validator_pins_wheel_and_rust_kinematics(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("9d3f8551c42bd12b43f47a1f3fe5e8c39ca0c2ff6d02c27b094ed0f5586c7655", text)
        self.assertIn('EXPECTED_RUST_KINEMATICS_VERSION = "1.0.3"', text)
        self.assertIn("installed_sources_byte_equal_to_wheel", text)


if __name__ == "__main__":
    unittest.main()
