import unittest

from reachy_stage4.rollback_inventory import (
    REQUIRED_SURFACES,
    SCHEMA_VERSION,
    compare_borrowed_condition,
)


def inventory(default="a"):
    return {
        "schema": SCHEMA_VERSION,
        "surfaces": {name: default * 64 for name in REQUIRED_SURFACES},
    }


class RollbackInventoryTests(unittest.TestCase):
    def test_exact_surface_match_still_requires_owner_acceptance(self):
        result = compare_borrowed_condition(inventory(), inventory())
        self.assertEqual(result["status"], "MATCH")
        self.assertTrue(result["all_reviewed_surfaces_match"])
        self.assertFalse(result["practical_equivalence_established"])
        self.assertFalse(result["literal_identity_claimed"])

    def test_difference_requires_owner_review(self):
        after = inventory()
        after["surfaces"]["daemon_launcher"] = "b" * 64
        result = compare_borrowed_condition(inventory(), after)
        self.assertEqual(result["status"], "DIFFERENCE_REQUIRES_OWNER_REVIEW")
        self.assertEqual(result["differences"][0]["surface"], "daemon_launcher")

    def test_missing_surface_fails_closed(self):
        after = inventory()
        del after["surfaces"]["asoundrc_state"]
        with self.assertRaisesRegex(ValueError, "surface mismatch"):
            compare_borrowed_condition(inventory(), after)


if __name__ == "__main__":
    unittest.main()
