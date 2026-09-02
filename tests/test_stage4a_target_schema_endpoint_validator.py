import ast
import inspect
import unittest

from scripts import validate_target_schema_endpoints


class TargetSchemaEndpointValidatorTests(unittest.TestCase):
    def test_validator_has_no_robot_or_network_client_import(self):
        source = inspect.getsource(validate_target_schema_endpoints)
        tree = ast.parse(source)
        forbidden_roots = {"requests", "websockets", "socket", "reachy_mini"}
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(forbidden_roots.isdisjoint(imported_roots))

    def test_validator_covers_both_route_surfaces_and_negative_control(self):
        source = inspect.getsource(validate_target_schema_endpoints)
        self.assertIn("/state/full", source)
        self.assertIn("/state/ws/full", source)
        self.assertIn("released_negative_control", source)
        self.assertIn("patched_positive_control", source)
        self.assertIn('"robot_commands_authorized": 0', source)


if __name__ == "__main__":
    unittest.main()
