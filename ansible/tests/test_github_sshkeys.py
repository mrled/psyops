"""Mocked GitHub API tests; no network access or real accounts required."""

import base64
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from ansible.module_utils.urls import open_url
from ansible.plugins.callback import CallbackBase

MODULE = Path(__file__).resolve().parents[1] / "roles/github_sshkeys/library/github_sshkeys.py"
SPEC = importlib.util.spec_from_file_location("github_sshkeys", MODULE)
github = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(github)


def key(letter):
    return (
        "ssh-ed25519 "
        + base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0\x20" + letter.encode() * 32).decode()
    )


def entry(letter="a", title="laptop", **extra):
    return {"title": title, "key": key(letter), **extra}


def desired(letter="a", comment="laptop"):
    return key(letter) + " " + comment


class Finished(Exception):
    def __init__(self, result):
        self.result = result


class GithubSSHKeysTests(unittest.TestCase):
    def setUp(self):
        self.module = Mock()
        self.module.params = {"token": "SECRET", "username": "Alice", "keys": [desired()]}
        self.module.check_mode = False
        self.module._diff = False
        self.module.exit_json.side_effect = lambda **kw: self.finish(kw)
        self.module.fail_json.side_effect = lambda **kw: self.finish({"failed": True, **kw})
        self.calls = []
        self.responses = [(200, {"login": "alice"}), (200, [])]
        self.fetch = patch.object(github, "open_url", side_effect=self.request)
        self.fetch.start()
        self.addCleanup(self.fetch.stop)
        self.constructor = patch.object(github, "AnsibleModule", return_value=self.module)
        self.constructor.start()
        self.addCleanup(self.constructor.stop)

    def finish(self, result):
        raise Finished(result)

    def request(self, url, **kwargs):
        self.calls.append((kwargs["method"], url.removeprefix("https://api.github.com"), kwargs))
        status, body = self.responses.pop(0)
        response = io.BytesIO(json.dumps(body).encode())
        response.getcode = lambda: status
        return response

    def run_module(self):
        with self.assertRaises(Finished) as caught:
            github.main()
        return caught.exception.result

    def methods(self):
        return [(method, path) for method, path, _ in self.calls]

    def test_noop_ignores_comments_and_login_case(self):
        self.responses[1] = (200, [entry(key=key("a") + " old comment", id=1)])
        self.assertFalse(self.run_module()["changed"])
        self.assertTrue(all(method == "GET" for method, _ in self.methods()))

    def test_secure_requests(self):
        self.responses.append((201, {}))
        self.run_module()
        for _, _, kwargs in self.calls:
            self.assertEqual(kwargs["follow_redirects"], "none")
            self.assertFalse(kwargs["use_netrc"])
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer SECRET")
            self.assertIn("Authorization", kwargs["unredirected_headers"])

    def test_pagination_empty_and_short_last_pages(self):
        self.module.params["keys"] = []
        self.module.check_mode = True
        self.module._diff = True
        for last_page in ([], [entry("b", id=101)]):
            with self.subTest(last_page=last_page):
                self.calls.clear()
                self.responses = [
                    (200, {"login": "alice"}),
                    (200, [entry(id=i + 1) for i in range(100)]),
                    (200, last_page),
                ]
                result = self.run_module()
                self.assertTrue(result["changed"])
                self.assertEqual(len(result["diff"]["before"].splitlines()), 100 + len(last_page))
                self.assertEqual(
                    self.methods(),
                    [
                        ("GET", "/user"),
                        ("GET", "/user/keys?per_page=100&page=1"),
                        ("GET", "/user/keys?per_page=100&page=2"),
                    ],
                )

    def test_check_mode_reports_diff_without_writes(self):
        self.module.check_mode = True
        self.module._diff = True
        self.responses[1] = (200, [entry("b", id=2)])
        result = self.run_module()
        self.assertTrue(result["changed"])
        self.assertEqual(result["diff"]["before"], desired("b") + "\n")
        self.assertEqual(result["diff"]["after"], desired() + "\n")
        rendered = CallbackBase()._get_diff(result["diff"])
        self.assertIn("-" + desired("b"), rendered)
        self.assertIn("+" + desired(), rendered)
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(
            self.methods(), [("GET", "/user"), ("GET", "/user/keys?per_page=100&page=1")]
        )

    def test_empty_deletes_all(self):
        self.module.params["keys"] = []
        self.responses[1] = (200, [entry(id=1), entry("b", id=2)])
        self.responses.extend([(204, None), (204, None)])
        self.assertTrue(self.run_module()["changed"])
        self.assertEqual(
            self.methods()[2:], [("DELETE", "/user/keys/1"), ("DELETE", "/user/keys/2")]
        )

    def test_account_mismatch_stops_before_listing(self):
        self.responses[0] = (200, {"login": "someone-else"})
        result = self.run_module()
        self.assertTrue(result["failed"])
        self.assertIn("username", result["msg"])
        self.assertFalse(result["changed"])
        self.assertEqual(self.methods(), [("GET", "/user")])

    def test_invalid_desired_entries_fail_before_api(self):
        invalid = [
            [key("a")],
            [desired(comment="")],
            [desired(comment=" \t  ")],
            [desired(comment="bad\ntitle")],
            [desired(comment="bad\rtitle")],
            [desired(comment="bad\0title")],
            ["ssh-ed25519 !!! laptop"],
            [desired().replace("ssh-ed25519", "ssh-rsa", 1)],
            ["restrict " + desired()],
            [entry()],
            [{"title": "missing key"}],
            [None],
        ]
        for entries in invalid:
            with self.subTest(entries=entries):
                self.module.params["keys"] = entries
                self.assertTrue(self.run_module()["failed"])
                self.assertEqual(self.calls, [])

    def test_full_comment_becomes_title_preserving_internal_whitespace(self):
        comment = "work  laptop\tGitHub key"
        self.module.params["keys"] = [
            " \t" + key("a").replace(" ", "\t ") + "\t  " + comment + " \t"
        ]
        self.module._diff = True
        self.responses.append((201, {}))
        result = self.run_module()
        self.assertTrue(result["changed"])
        self.assertEqual(result["diff"]["after"], desired(comment=comment) + "\n")
        self.assertEqual(json.loads(self.calls[2][2]["data"]), entry(title=comment))

    def test_duplicate_key_with_different_comments_rejected_before_api(self):
        self.module.params["keys"] = [desired(comment="first"), desired(comment="second")]
        result = self.run_module()
        self.assertTrue(result["failed"])
        self.assertIn("Duplicate", result["msg"])
        self.assertEqual(self.calls, [])

    def test_additions_then_title_replacement_then_unmanaged_deletions(self):
        self.module.params["keys"] = [desired(comment="new name"), desired("b", "new name")]
        self.responses[1] = (200, [entry(id=1), entry("c", id=3)])
        self.responses.extend([(201, {}), (204, None), (201, {}), (204, None)])
        self.assertTrue(self.run_module()["changed"])
        self.assertEqual(
            self.methods()[2:],
            [
                ("POST", "/user/keys"),
                ("DELETE", "/user/keys/1"),
                ("POST", "/user/keys"),
                ("DELETE", "/user/keys/3"),
            ],
        )
        self.assertEqual(json.loads(self.calls[2][2]["data"]), entry("b", "new name"))
        self.assertEqual(json.loads(self.calls[4][2]["data"]), entry("a", "new name"))

    def test_failed_title_recreation_stops_further_deletions(self):
        self.responses[1] = (200, [entry(title="old", id=1), entry("c", id=3)])
        self.responses.extend([(204, None), (422, {})])
        result = self.run_module()
        self.assertTrue(result["failed"])
        self.assertTrue(result["changed"])
        self.assertEqual(self.methods()[2:], [("DELETE", "/user/keys/1"), ("POST", "/user/keys")])

    def test_bad_api_response_never_mutates(self):
        for response in [(403, {"message": "SECRET"}), (200, {}), (200, [entry(id="bad")])]:
            with self.subTest(response=response):
                self.calls.clear()
                self.responses = [(200, {"login": "alice"}), response]
                result = self.run_module()
                self.assertTrue(result["failed"])
                self.assertNotIn("SECRET", json.dumps(result))
                self.assertTrue(all(method == "GET" for method, _ in self.methods()))

    def test_partial_addition_failure_prevents_all_deletions(self):
        self.module.params["keys"] = [desired("a"), desired("b"), desired("c", comment="renamed")]
        self.responses[1] = (200, [entry("c", id=3), entry("d", id=4)])
        self.responses.extend([(201, {}), (422, {"message": "SECRET"})])
        result = self.run_module()
        self.assertTrue(result["failed"])
        self.assertTrue(result["changed"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual([method for method, _ in self.methods()], ["GET", "GET", "POST", "POST"])

    def test_invalid_json_and_read_errors_are_safe_and_close_response(self):
        for response in (io.BytesIO(b"SECRET"), Mock()):
            response.getcode = lambda: 200
            if isinstance(response, Mock):
                response.read.side_effect = OSError("SECRET")
            with (
                self.subTest(response=response),
                patch.object(github, "open_url", return_value=response),
            ):
                result = self.run_module()
                self.assertTrue(result["failed"])
                self.assertNotIn("SECRET", json.dumps(result))
                if isinstance(response, Mock):
                    response.close.assert_called_once()
                else:
                    self.assertTrue(response.closed)

    def test_real_helper_errors_are_sanitized_and_track_write_attempts(self):
        for method, error_type in (("GET", OSError), ("POST", URLError)):
            with (
                self.subTest(method=method),
                patch.object(github, "open_url", side_effect=open_url),
                patch(
                    "ansible.module_utils.urls.urllib.request.urlopen",
                    side_effect=error_type("SECRET transport diagnostics"),
                ) as network,
            ):
                api = github.GitHub(self.module)
                with self.assertRaises(github.KeyErrorSafe) as caught:
                    api.request(method, "/user/keys", 200)
                self.assertEqual(api.changed, method != "GET")
                self.assertNotIn("SECRET", str(caught.exception))
                self.assertNotIn("transport diagnostics", str(caught.exception))
                network.assert_called_once()

    def test_real_helper_http_error_keeps_only_status_and_closes_response(self):
        body = io.BytesIO(b"SECRET response body")
        error = HTTPError("https://SECRET", 302, "SECRET reason", {}, body)
        with (
            patch.object(github, "open_url", side_effect=open_url),
            patch("ansible.module_utils.urls.urllib.request.urlopen", side_effect=error),
        ):
            result = self.run_module()
        self.assertTrue(result["failed"])
        self.assertEqual(result["msg"], "GitHub GET /user failed (HTTP 302)")
        self.assertFalse(result["changed"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertTrue(body.closed)

    def test_keys_required_with_real_ansible_module(self):
        process = subprocess.run(
            [sys.executable, str(MODULE)],
            input=json.dumps({"ANSIBLE_MODULE_ARGS": {"token": "SECRET", "username": "alice"}}),
            capture_output=True,
            text=True,
            check=False,
        )
        result = json.loads(process.stdout)
        self.assertTrue(result["failed"])
        self.assertIn("keys", result["msg"])
        self.assertNotIn("SECRET", process.stdout)


if __name__ == "__main__":
    unittest.main()
