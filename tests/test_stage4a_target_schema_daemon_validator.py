import inspect
import unittest

from scripts import validate_target_schema_daemon


class TargetSchemaDaemonValidatorTests(unittest.TestCase):
    def test_loopback_classifier_rejects_robot_and_unspecified_addresses(self):
        self.assertTrue(validate_target_schema_daemon._is_loopback_host("127.0.0.1"))
        self.assertTrue(validate_target_schema_daemon._is_loopback_host("::1"))
        self.assertTrue(validate_target_schema_daemon._is_loopback_host("localhost"))
        self.assertFalse(validate_target_schema_daemon._is_loopback_host("0.0.0.0"))
        self.assertFalse(validate_target_schema_daemon._is_loopback_host("192.168.1.251"))

    def test_harness_requires_mockup_and_disables_external_surfaces(self):
        source = inspect.getsource(validate_target_schema_daemon)
        for required in (
            '"--mockup-sim"',
            '"--no-media"',
            '"127.0.0.1"',
            '"--dataset-update-interval"',
            'daemon_main.MdnsServiceRegistration = DisabledMdns',
            'daemon_main.startup_app_config.get_startup_app = lambda: None',
            '"robot_connections": 0',
            '"robot_commands_sent": 0',
            '"robot_commands_authorized": 0',
        ):
            self.assertIn(required, source)

    def test_harness_covers_negative_control_and_all_three_surfaces(self):
        source = inspect.getsource(validate_target_schema_daemon)
        self.assertIn("released_negative_control", source)
        self.assertIn("patched_positive_control", source)
        self.assertIn("/api/state/full", source)
        self.assertIn("/api/state/ws/full", source)
        self.assertIn('("matrix", True)', source)
        self.assertIn('("xyz_rpy", False)', source)

    def test_harness_binds_sources_to_wheel_and_patch(self):
        source = inspect.getsource(validate_target_schema_daemon)
        self.assertIn("released_files_match_wheel_byte_for_byte", source)
        self.assertIn("patched_tree_reverse_checks_against_patch", source)
        self.assertIn('"wheel_sha256"', source)
        self.assertIn('"patch_sha256"', source)
        self.assertIn('"--reverse"', source)


if __name__ == "__main__":
    unittest.main()
