"""Resolve exactly one GitHub release asset on the Ansible controller."""
import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import quote

from ansible.errors import AnsibleError
from ansible.module_utils.urls import open_url
from ansible.plugins.lookup import LookupBase

DOCUMENTATION = r"""
name: github_release_asset
author: psyops maintainers
short_description: Select one asset from a GitHub release
description:
  - Queries the GitHub REST API on the controller using Ansible's proxy and TLS support.
  - Returns exactly one asset with flattened release metadata; does not download the asset.
options:
  _terms:
    description: A single GitHub repository in owner/repo form.
    required: true
    type: list
    elements: str
  asset_regex:
    description: Python regular expression searched against asset names. Must match exactly one asset.
    required: true
    type: str
  version:
    description: Exact release tag, or latest to use GitHub's latest release endpoint.
    type: str
    default: latest
  token:
    description:
      - Optional GitHub authentication token. Defaults to the controller's GITHUB_TOKEN environment variable.
      - Pass an empty string to disable authentication even when GITHUB_TOKEN is set.
    type: str
    env:
      - name: GITHUB_TOKEN
"""

EXAMPLES = r"""
- name: Resolve the latest Linux asset
  ansible.builtin.set_fact:
    release_asset: "{{ lookup('github_release_asset', 'owner/repo', asset_regex='linux-amd64[.]tar[.]gz$') }}"

- name: Resolve an exact release tag
  ansible.builtin.set_fact:
    pinned_asset: "{{ lookup('github_release_asset', 'owner/repo', asset_regex='linux-amd64[.]tar[.]gz$', version='v1.2.3') }}"
"""

RETURN = r"""
_raw:
  description: One selected asset with release metadata (lookup returns the single dictionary).
  type: list
  elements: dict
  contains:
    name:
      description: Asset filename.
      type: str
    browser_download_url:
      description: Asset download URL.
      type: str
    tag_name:
      description: Release tag.
      type: str
    html_url:
      description: Release page URL.
      type: str
"""


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        if (len(terms) != 1 or not isinstance(terms[0], str)
                or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", terms[0])):
            raise AnsibleError("github_release_asset requires one repository in owner/repo form")
        repository = terms[0]
        pattern = kwargs.get("asset_regex")
        if not isinstance(pattern, str) or not pattern:
            raise AnsibleError("github_release_asset requires a nonempty asset_regex string")
        try:
            regex = re.compile(pattern)
        except re.error:
            raise AnsibleError("github_release_asset: asset_regex is invalid; check Python regex syntax") from None
        version = kwargs.get("version", "latest")
        if not isinstance(version, str) or not version:
            raise AnsibleError("github_release_asset: version must be a nonempty exact tag or 'latest'")
        token = kwargs.get("token", os.environ.get("GITHUB_TOKEN", ""))
        if not isinstance(token, str):
            raise AnsibleError("github_release_asset: token must be a string")

        endpoint = "latest" if version == "latest" else "tags/" + quote(version, safe="")
        url = "https://api.github.com/repos/{}/releases/{}".format(repository, endpoint)
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        # Never include exception messages or response bodies: either can contain credentials.
        try:
            response = open_url(url, headers=headers, timeout=30)
            try:
                body = response.read()
            finally:
                response.close()
        except HTTPError as error:
            raise AnsibleError(
                "github_release_asset: GitHub HTTP {} for {}; check the repository/tag, "
                "token permissions and API rate limit".format(error.code, repository)
            ) from None
        except Exception:
            raise AnsibleError(
                "github_release_asset: request failed for {}; check network, proxy and TLS "
                "settings (timeout: 30 seconds)".format(repository)
            ) from None
        try:
            release = json.loads(body)
        except (ValueError, TypeError, UnicodeError):
            raise AnsibleError(
                "github_release_asset: invalid JSON from GitHub for {}; check the API/proxy response".format(repository)
            ) from None

        def nonempty_string(value):
            return isinstance(value, str) and bool(value)

        if (not isinstance(release, dict)
                or not nonempty_string(release.get("tag_name"))
                or not nonempty_string(release.get("html_url"))
                or not isinstance(release.get("assets"), list)):
            raise AnsibleError("github_release_asset: invalid release schema; expected tag_name, html_url and assets list")
        matches = []
        for asset in release["assets"]:
            if (not isinstance(asset, dict)
                    or not nonempty_string(asset.get("name"))
                    or not nonempty_string(asset.get("browser_download_url"))):
                raise AnsibleError("github_release_asset: invalid asset schema; expected name and browser_download_url strings")
            if regex.search(asset["name"]):
                matches.append(asset)
        if len(matches) != 1:
            raise AnsibleError(
                "github_release_asset: asset_regex matched {} assets in {}; require exactly one; "
                "adjust asset_regex or select a different version".format(len(matches), repository)
            )
        asset = matches[0]
        return [{"name": asset["name"], "browser_download_url": asset["browser_download_url"],
                 "tag_name": release["tag_name"], "html_url": release["html_url"]}]
