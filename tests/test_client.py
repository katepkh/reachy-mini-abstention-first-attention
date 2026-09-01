import unittest
from unittest.mock import Mock, patch

from reachy_doa.client import ReadOnlyDoAClient


class ReadOnlyDoAClientTests(unittest.TestCase):
    @patch("reachy_doa.client.requests.Session")
    def test_reuses_one_session_for_repeated_exact_gets(self, session_factory) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"angle": 1.25, "speech_detected": True}
        session.get.return_value = response
        session_factory.return_value = session

        client = ReadOnlyDoAClient("192.168.1.251")
        first = client.read()
        second = client.read()

        session_factory.assert_called_once_with()
        self.assertFalse(session.trust_env)
        self.assertTrue(first.valid)
        self.assertTrue(second.valid)
        self.assertEqual(session.get.call_count, 2)
        for call in session.get.call_args_list:
            self.assertEqual(
                call.args,
                ("http://192.168.1.251:8000/api/state/doa",),
            )
            self.assertEqual(call.kwargs["timeout"], 1.0)
            self.assertFalse(call.kwargs["allow_redirects"])

        client.close()
        session.close.assert_called_once_with()

    @patch("reachy_doa.client.requests.Session")
    def test_invalid_payload_is_reported_without_retry(self, session_factory) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"angle": "invalid", "speech_detected": True}
        session.get.return_value = response
        session_factory.return_value = session

        reading = ReadOnlyDoAClient("192.168.1.251").read()

        self.assertFalse(reading.valid)
        self.assertEqual(session.get.call_count, 1)
        self.assertIn("numeric angle", reading.error)


if __name__ == "__main__":
    unittest.main()
