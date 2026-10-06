"""Controller lookup tests; no Ansible installation or network required."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


try:
    from ansible.errors import AnsibleError
    from ansible.plugins.lookup import LookupBase
    from ansible.module_utils.urls import open_url
except ImportError:
    class AnsibleError(Exception):
        pass

    class LookupBase:
        pass

    def open_url(*args, **kwargs):
        raise AssertionError("Network access must be mocked")

    # Supply only the imports this plugin needs, including parent packages.
    for name in ("ansible", "ansible.errors", "ansible.plugins",
                 "ansible.plugins.lookup", "ansible.module_utils",
                 "ansible.module_utils.urls"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["ansible.errors"].AnsibleError = AnsibleError
    sys.modules["ansible.plugins.lookup"].LookupBase = LookupBase
    sys.modules["ansible.module_utils.urls"].open_url = open_url

PLUGIN_PATH = Path(__file__).resolve().parents[1] / "lookup_plugins" / "github_release_asset.py"
spec = importlib.util.spec_from_file_location("github_release_asset", PLUGIN_PATH)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class GithubReleaseAssetTests(unittest.TestCase):
    def setUp(self):
        self.lookup = plugin.LookupModule()
        self.release = {
            "tag_name": "v1.2.3",
            "html_url": "https://github.com/owner/repo/releases/tag/v1.2.3",
            "assets": [
                {"name": "app-linux-amd64.tar.gz", "browser_download_url": "https://example.com/linux"},
                {"name": "app-darwin-amd64.tar.gz", "browser_download_url": "https://example.com/darwin"},
            ],
        }
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.request = patch.object(plugin, "open_url")
        self.open_url = self.request.start()
        self.addCleanup(self.request.stop)
        self.respond(self.release)

    def respond(self, value):
        self.response = io.BytesIO(json.dumps(value).encode())
        self.open_url.return_value = self.response

    def run_lookup(self, **kwargs):
        return self.lookup.run(["owner/repo"], asset_regex=r"linux.*\.tar\.gz$", **kwargs)

    def test_latest_returns_one_flattened_dict_and_closes_response(self):
        result = self.run_lookup()
        self.assertEqual(result, [{
            "name": "app-linux-amd64.tar.gz",
            "browser_download_url": "https://example.com/linux",
            "tag_name": "v1.2.3",
            "html_url": self.release["html_url"],
        }])
        args, kwargs = self.open_url.call_args
        self.assertEqual(args[0], "https://api.github.com/repos/owner/repo/releases/latest")
        self.assertEqual(kwargs["timeout"], 30)
        self.assertNotIn("Authorization", kwargs["headers"])
        self.assertTrue(self.response.closed)

    def test_pinned_tag_is_exact_and_url_escaped(self):
        self.run_lookup(version="release/1.2+test #?")
        self.assertEqual(self.open_url.call_args.args[0],
                         "https://api.github.com/repos/owner/repo/releases/tags/release%2F1.2%2Btest%20%23%3F")

    def test_regex_search_not_fullmatch(self):
        self.assertEqual(self.lookup.run(["owner/repo"], asset_regex="linux")[0]["name"],
                         "app-linux-amd64.tar.gz")

    def test_ambiguous_regex(self):
        with self.assertRaisesRegex(AnsibleError, "matched 2.*exactly one"):
            self.lookup.run(["owner/repo"], asset_regex="amd64")

    def test_no_match(self):
        with self.assertRaisesRegex(AnsibleError, "matched 0.*exactly one"):
            self.lookup.run(["owner/repo"], asset_regex="windows")

    def test_invalid_regex_does_not_request(self):
        with self.assertRaisesRegex(AnsibleError, "asset_regex.*invalid"):
            self.lookup.run(["owner/repo"], asset_regex="[")
        self.open_url.assert_not_called()

    def test_invalid_inputs(self):
        cases = [([], {"asset_regex": "linux"}),
                 (["owner/repo", "other/repo"], {"asset_regex": "linux"}),
                 (["https://github.com/owner/repo"], {"asset_regex": "linux"}),
                 (["owner/repo"], {}),
                 (["owner/repo"], {"asset_regex": 7}),
                 (["owner/repo"], {"asset_regex": "linux", "version": ""})]
        for terms, kwargs in cases:
            with self.subTest(terms=terms, kwargs=kwargs), self.assertRaises(AnsibleError):
                self.lookup.run(terms, **kwargs)
        self.open_url.assert_not_called()

    def test_token_environment_and_override(self):
        os.environ["GITHUB_TOKEN"] = "environment-secret"
        self.run_lookup()
        self.assertEqual(self.open_url.call_args.kwargs["headers"]["Authorization"],
                         "Bearer environment-secret")
        self.respond(self.release)
        self.run_lookup(token="explicit-secret")
        self.assertEqual(self.open_url.call_args.kwargs["headers"]["Authorization"],
                         "Bearer explicit-secret")
        self.respond(self.release)
        self.run_lookup(token="")
        self.assertNotIn("Authorization", self.open_url.call_args.kwargs["headers"])

    def test_request_errors_are_actionable_and_do_not_leak_token(self):
        secret = "do-not-disclose-this-token"
        errors = [HTTPError("https://example.com", 403, secret, {}, None),
                  URLError(secret), TimeoutError(secret), OSError(secret)]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.open_url.side_effect = error
                with self.assertRaises(AnsibleError) as caught:
                    self.run_lookup(token=secret)
                self.assertNotIn(secret, str(caught.exception))
                self.assertIn("owner/repo", str(caught.exception))
        self.assertIn("network", str(caught.exception))

    def test_read_error_is_wrapped(self):
        self.open_url.return_value = unittest.mock.Mock()
        self.open_url.return_value.read.side_effect = OSError("secret")
        with self.assertRaisesRegex(AnsibleError, "network"):
            self.run_lookup()
        self.open_url.return_value.close.assert_called_once()

    def test_invalid_json(self):
        self.open_url.return_value = io.BytesIO(b"not JSON")
        with self.assertRaisesRegex(AnsibleError, "JSON"):
            self.run_lookup()

    def test_invalid_schema(self):
        values = [None, [], {}, {**self.release, "tag_name": None},
                  {**self.release, "html_url": 42},
                  {**self.release, "assets": {}},
                  {**self.release, "assets": [None]},
                  {**self.release, "assets": [{"name": "linux"}]},
                  {**self.release, "assets": [{"name": 42, "browser_download_url": "x"}]}]
        for value in values:
            with self.subTest(value=value):
                self.respond(value)
                with self.assertRaisesRegex(AnsibleError, "schema"):
                    self.run_lookup()


if __name__ == "__main__":
    unittest.main()
