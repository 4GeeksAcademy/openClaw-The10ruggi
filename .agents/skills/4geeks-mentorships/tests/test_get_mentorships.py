"""Focused offline tests for the 4Geeks mentorship read-only helper."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "get_mentorships.py"
spec = importlib.util.spec_from_file_location("get_mentorships", SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class FakeResponse:
    def __init__(self, status=200, body=b"[]"):
        self.code = status
        self.body = body
        self.closed = False

    def read(self, limit=-1):
        return self.body[:limit]

    def close(self):
        self.closed = True


class HelperTests(unittest.TestCase):
    def test_missing_token_makes_no_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(helper, "build_opener") as opener:
            payload, error = helper.request_json(helper.SESSIONS_PATH)
        self.assertIsNone(payload)
        self.assertEqual(error, {"error": "token_missing"})
        opener.assert_not_called()

    def test_request_uses_gateway_token_and_get_only(self):
        response = FakeResponse(body=b'{"ok":true}')
        opener = type("Opener", (), {"open": lambda self, req, timeout: (captured.update(request=req, timeout=timeout) or response)})()
        captured = {}
        with patch.dict(os.environ, {"TOKEN_4GEEKS": "unit-secret"}), patch.object(
            helper, "build_opener", return_value=opener
        ):
            payload, error = helper.request_json(helper.MENTORS_PATH)
        self.assertEqual(payload, {"ok": True})
        self.assertIsNone(error)
        self.assertEqual(captured["request"].get_method(), "GET")
        self.assertEqual(captured["request"].get_header("Authorization"), "Token unit-secret")
        self.assertEqual(captured["timeout"], helper.TIMEOUT_SECONDS)
        self.assertTrue(response.closed)

    def test_http_error_is_sanitized(self):
        error_response = HTTPError(
            helper.BASE_URL + helper.SESSIONS_PATH, 403, "forbidden unit-secret", {}, io.BytesIO(b"unit-secret")
        )
        opener = type("Opener", (), {"open": lambda self, req, timeout: (_ for _ in ()).throw(error_response)})()
        with patch.dict(os.environ, {"TOKEN_4GEEKS": "unit-secret"}), patch.object(
            helper, "build_opener", return_value=opener
        ):
            payload, error = helper.request_json(helper.SESSIONS_PATH)
        self.assertIsNone(payload)
        self.assertEqual(error, {"error": "http_error", "http_status": 403})
        self.assertNotIn("unit-secret", json.dumps(error))

    def test_emit_redacts_token(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"TOKEN_4GEEKS": "unit-secret"}), patch("sys.stdout", output):
            helper.emit({"name": "unit-secret"})
        self.assertNotIn("unit-secret", output.getvalue())
        self.assertIn("[REDACTED]", output.getvalue())

    def test_mentor_fields_and_accent_insensitive_name_query(self):
        payload = [
            {"user": {"first_name": "José", "last_name": "Álvarez", "profile": {"avatar_url": "x"}}},
            {"user": {"first_name": "Ada", "last_name": "Lovelace"}},
        ]
        with patch.object(helper, "request_json", return_value=(payload, None)):
            result = helper.fetch_mentors("jose alvarez")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0], {"name": "José Álvarez", "mentor_slug": None, "services": []})
        self.assertNotIn("x", json.dumps(result))

    def test_empty_sessions_is_successful_empty_list(self):
        with patch.object(helper, "request_json", return_value=([], None)):
            result = helper.fetch_sessions()
        self.assertEqual(result, {"http_status": 200, "count": 0, "results": []})

    def test_session_date_and_upcoming_require_real_future_start_and_pending(self):
        rows = [
            {"status": "PENDING", "starts_at": "2099-01-02T12:00:00Z"},
            {"status": "PENDING", "started_at": "2099-01-02T12:00:00Z"},
            {"status": "DONE", "starts_at": "2099-01-02T12:00:00Z"},
        ]
        with patch.object(helper, "request_json", return_value=(rows, None)):
            result = helper.fetch_sessions()
        self.assertEqual(result["count"], 3)
        self.assertEqual([row["upcoming"] for row in result["results"]], [True, False, False])

    def test_http_and_invalid_structure_are_not_empty_results(self):
        with patch.object(helper, "request_json", return_value=(None, {"error": "http_error", "http_status": 500})):
            http_result = helper.fetch_sessions()
        with patch.object(helper, "request_json", return_value=({"unexpected": []}, None)):
            structure_result = helper.fetch_mentors()
        self.assertEqual(http_result, {"error": "http_error", "http_status": 500})
        self.assertEqual(structure_result, {"error": "unexpected_structure", "http_status": 200})
        self.assertNotIn("results", http_result)

    def test_cli_arguments_and_machine_readable_output(self):
        env = {key: value for key, value in os.environ.items() if key != "TOKEN_4GEEKS"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "sessions"], capture_output=True, text=True, env=env, check=False
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"error": "token_missing"})
        bad_args = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env, check=False
        )
        self.assertEqual(bad_args.returncode, 2)


if __name__ == "__main__":
    unittest.main()
