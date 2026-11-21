#!/usr/bin/python
"""Exclusively manage a GitHub account's SSH authentication keys."""

import base64
import binascii
import json
from contextlib import suppress
from urllib.error import HTTPError

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url

DOCUMENTATION = r"""
---
module: github_sshkeys
short_description: Exclusively manage GitHub SSH authentication keys
description:
  - Manages the entire authenticated account's SSH authentication key set, not signing keys.
  - Uses only https://api.github.com and refuses redirects.
options:
  token:
    description: GitHub token with permission to read and write account authentication keys.
    type: str
    required: true
  username:
    description: Expected account login, verified case insensitively against GET /user.
    type: str
    required: true
  keys:
    description:
      - Complete desired key set. An explicit empty list removes all authentication keys.
      - Each entry must be a plain OpenSSH public key with a nonempty comment.
      - The full comment becomes the GitHub title, with outer whitespace stripped.
      - Keys are compared by type and decoded base64 data; comments determine titles.
      - Duplicate key material is rejected. Different keys may share a title.
    type: list
    elements: str
    required: true
notes:
  - All desired entries are validated and all current keys read before any writes.
  - Entirely new keys are added before title replacements or unmanaged-key deletions.
  - GitHub has no authentication-key update endpoint. A title change deletes and recreates
    that key, causing a temporary gap. If recreation fails, that key remains absent.
  - Any failed write stops processing immediately. No unmanaged keys are deleted after
    an addition fails; successful earlier writes are not rolled back.
  - Check mode reads the API and reports the plan without writing. Diff contains public
    keys and titles only. Validation checks key syntax, not full cryptographic validity.
  - Write failures can have uncertain outcomes; changed is conservatively true once a
    write has been attempted. Concurrent account changes are not locked out.
author:
  - psyops
"""

EXAMPLES = r"""
- name: Manage the complete authentication key set
  github_sshkeys:
    token: "{{ github_token }}"
    username: example
    keys:
      - "{{ laptop_public_key_with_comment }}"

- name: Remove all authentication keys
  github_sshkeys:
    token: "{{ github_token }}"
    username: example
    keys: []
"""

RETURN = r"""
changed:
  description: Whether changes were needed (or a write was attempted on failure).
  type: bool
  returned: always
diff:
  description: Before and desired public keys and titles, without API IDs or token.
  type: dict
  returned: success when diff mode is enabled
"""

API = "https://api.github.com"
KEY_TYPES = {
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
}


class KeyErrorSafe(Exception):
    """An error message safe to return without API bodies or transport diagnostics."""


def normalize_key(value):
    """Validate plain-key syntax and return canonical material without comments."""
    if not isinstance(value, str) or "\n" in value or "\r" in value:
        raise KeyErrorSafe("Expected a single SSH public key line")
    fields = value.split()
    if len(fields) < 2 or fields[0] not in KEY_TYPES:
        raise KeyErrorSafe("Unsupported SSH key type or invalid public key syntax")
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except (ValueError, binascii.Error) as error:
        raise KeyErrorSafe("Invalid SSH public key base64") from error
    size = int.from_bytes(blob[:4], "big")
    if blob[4 : 4 + size] != fields[0].encode() or len(blob) <= 4 + size:
        raise KeyErrorSafe("Invalid or mismatched SSH public key blob type")
    if fields[0] == "ssh-ed25519" and (blob[15:19] != b"\0\0\0\x20" or len(blob) != 51):
        raise KeyErrorSafe("Invalid Ed25519 public key length")
    return fields[0] + " " + base64.b64encode(blob).decode("ascii")


def desired_keys(entries):
    if not isinstance(entries, list):
        raise KeyErrorSafe("keys must be an explicit list")
    result = []
    seen = set()
    for entry in entries:
        key = normalize_key(entry)
        fields = entry.split(None, 2)
        if len(fields) != 3 or not fields[2].strip():
            raise KeyErrorSafe(
                "Each desired SSH public key requires a nonempty comment for its title"
            )
        title = fields[2].strip()
        if any(c in title for c in "\r\n\0"):
            raise KeyErrorSafe("Key comment must be single-line and contain no NUL characters")
        if key in seen:
            raise KeyErrorSafe("Duplicate desired SSH key material")
        seen.add(key)
        result.append({"title": title, "key": key})
    return result


class GitHub:
    def __init__(self, module):
        self.module = module
        self.changed = False

    def request(self, method, path, expected, data=None):
        response = None
        if method != "GET":
            # A timeout may happen after the server commits the operation.
            self.changed = True
        try:
            response = open_url(
                API + path,
                method=method,
                timeout=30,
                headers={
                    "Authorization": "Bearer " + self.module.params["token"],
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                data=json.dumps(data) if data is not None else None,
                follow_redirects="none",
                use_netrc=False,
                unredirected_headers=["Authorization"],
            )
            status = response.getcode()
            if status != expected:
                # Never echo helper messages, response bodies, or arbitrary status values.
                code = str(status) if type(status) is int else "unknown"
                raise KeyErrorSafe(f"GitHub {method} {path} failed (HTTP {code})")
            if method == "GET":
                return json.loads(response.read())
            return None
        except HTTPError as error:
            # HTTP errors are also responses; close them without exposing their contents.
            response = error
            code = str(error.code) if type(error.code) is int else "unknown"
            raise KeyErrorSafe(f"GitHub {method} {path} failed (HTTP {code})") from error
        except KeyErrorSafe:
            raise
        except Exception as error:
            # Transport exceptions can embed credentials; never forward their text.
            raise KeyErrorSafe(
                f"GitHub {method} {path} failed (network or invalid JSON response)"
            ) from error
        finally:
            if response is not None:
                with suppress(Exception):
                    response.close()

    def current_keys(self, username):
        user = self.request("GET", "/user", 200)
        if not isinstance(user, dict) or not isinstance(user.get("login"), str):
            raise KeyErrorSafe("Invalid GitHub account response")
        if user["login"].casefold() != username.casefold():
            raise KeyErrorSafe("Authenticated GitHub account does not match username")
        result = []
        ids = set()
        page = 1
        while True:
            entries = self.request("GET", f"/user/keys?per_page=100&page={page}", 200)
            if not isinstance(entries, list):
                raise KeyErrorSafe("Invalid GitHub keys response")
            for entry in entries:
                if (
                    not isinstance(entry, dict)
                    or type(entry.get("id")) is not int
                    or entry["id"] <= 0
                    or entry["id"] in ids
                    or not isinstance(entry.get("title"), str)
                ):
                    raise KeyErrorSafe("Invalid GitHub key response or repeated page")
                ids.add(entry["id"])
                result.append(
                    {
                        "id": entry["id"],
                        "title": entry["title"],
                        "key": normalize_key(entry.get("key")),
                    }
                )
            if len(entries) < 100:
                return result
            page += 1


def plan_changes(current, desired):
    remaining = list(current)
    additions, replacements = [], []
    for entry in desired:
        matches = [old for old in remaining if old["key"] == entry["key"]]
        if not matches:
            additions.append(entry)
            continue
        old = next((old for old in matches if old["title"] == entry["title"]), matches[0])
        remaining.remove(old)
        if old["title"] != entry["title"]:
            replacements.append((old, entry))
    return additions, replacements, remaining


def render_keys(entries):
    """Render stable, line-oriented public keys for Ansible's diff callback."""
    return "".join(sorted(f"{entry['key']} {entry['title']}\n" for entry in entries))


def main():
    module = AnsibleModule(
        argument_spec={
            "token": {"type": "str", "required": True, "no_log": True},
            "username": {"type": "str", "required": True},
            "keys": {
                "type": "list",
                "elements": "str",
                "required": True,
            },
        },
        supports_check_mode=True,
    )
    api = GitHub(module)
    try:
        desired = desired_keys(module.params["keys"])
        if not module.params["username"].strip() or not module.params["token"].strip():
            raise KeyErrorSafe("username and token must be nonempty")
        current = api.current_keys(module.params["username"])
        additions, replacements, removals = plan_changes(current, desired)
        changed = bool(additions or replacements or removals)
        if not module.check_mode:
            for entry in additions:
                api.request("POST", "/user/keys", 201, entry)
            for old, entry in replacements:
                api.request("DELETE", f"/user/keys/{old['id']}", 204)
                api.request("POST", "/user/keys", 201, entry)
            for old in removals:
                api.request("DELETE", f"/user/keys/{old['id']}", 204)
        result = {"changed": changed}
        if module._diff:
            result["diff"] = {
                "before_header": "GitHub authentication keys (current)",
                "after_header": "GitHub authentication keys (desired)",
                "before": render_keys(current),
                "after": render_keys(desired),
            }
        module.exit_json(**result)
    except KeyErrorSafe as error:
        module.fail_json(msg=str(error), changed=api.changed)


if __name__ == "__main__":
    main()
