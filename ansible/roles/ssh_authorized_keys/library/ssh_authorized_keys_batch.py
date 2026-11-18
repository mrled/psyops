#!/usr/bin/python
"""Prototype: exclusively manage plain public keys for a batch of existing users.

Why use this instead of ansible.posix.authorized_key?
This implements the validation that authorized_key does,
but also adds a file header and sets the file contents in a single roundtrip.
"""

import base64
import binascii
import os
import pwd
import tempfile
from dataclasses import dataclass

from ansible.module_utils.basic import AnsibleModule

DEFAULT_HEADER = "Ansible managed"
KEY_TYPES = {
    "ssh-ed25519",
    "ssh-rsa",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
}


@dataclass
class UserKeys:
    user: str
    keys: list[str]


@dataclass
class UserPlan:
    account: pwd.struct_passwd
    content: bytes


@dataclass
class UserResult:
    changed: bool
    diff: list[dict]


def validate_key(key: str) -> None:
    """Check plain-key syntax and the SSH blob's type, not cryptographic validity."""
    fields = key.split()
    if "\n" in key or "\r" in key or len(fields) < 2:
        raise ValueError("expected a single SSH public key line")
    if fields[0] not in KEY_TYPES:
        raise ValueError(f"unsupported SSH key type or key options: {fields[0]!r}")
    blob = base64.b64decode(fields[1], validate=True)
    size = int.from_bytes(blob[:4], "big")
    if blob[4 : 4 + size] != fields[0].encode() or len(blob) <= 4 + size:
        raise ValueError("SSH key blob has an invalid or mismatched key type")
    if fields[0] == "ssh-ed25519" and (blob[15:19] != b"\x00\x00\x00\x20" or len(blob) != 51):
        raise ValueError("invalid Ed25519 public key length")


def prepare_users(users: list[UserKeys], header: str) -> list[UserPlan]:
    """Validate the entire batch before touching any account's files."""
    commented_header = "".join("# " + line + "\n" for line in header.splitlines())
    plans = []
    for entry in users:
        account = pwd.getpwnam(entry.user)
        for index, key in enumerate(entry.keys, start=1):
            try:
                validate_key(key)
            except ValueError as error:
                raise ValueError(f"Invalid key {index} for {entry.user}: {error}") from error
        content = (commented_header + "".join(key.strip() + "\n" for key in entry.keys)).encode()
        plans.append(UserPlan(account=account, content=content))
    return plans


def manage_user(module: AnsibleModule, plan: UserPlan) -> UserResult:
    """Replace one account's keys and enforce ownership and permissions."""
    account, content = plan.account, plan.content
    directory = os.path.join(account.pw_dir, ".ssh")
    path = os.path.join(directory, "authorized_keys")
    # This prototype deliberately refuses symlinks rather than following them.
    if os.path.islink(directory) or os.path.islink(path):
        raise ValueError(f"refusing symlink: {path}")
    current = None
    if os.path.exists(path):
        with open(path, "rb") as stream:
            current = stream.read()
    diffs = []
    if module._diff and current != content:
        diffs.append(dict(
            before_header=path,
            after_header=path,
            before=(current or b"").decode("utf-8", errors="replace"),
            after=content.decode("utf-8"),
        ))
    if not module.check_mode:
        os.makedirs(directory, mode=0o700, exist_ok=True)
    changed = False
    for target, mode in ((directory, "0700"), (path, "0600")):
        if target == path and current != content:
            changed = True
            if not module.check_mode:
                fd, temporary = tempfile.mkstemp(dir=module.tmpdir)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                module.atomic_move(temporary, path)
        if os.path.exists(target):
            attrs = dict(
                path=target, owner=str(account.pw_uid), group=str(account.pw_gid), mode=mode
            )
            attrs_diff = {}
            changed = module.set_fs_attributes_if_different(
                module.load_file_common_arguments(attrs), changed, diff=attrs_diff
            )
            if module._diff and attrs_diff and (target != path or current is not None):
                attrs_diff.update(before_header=target, after_header=target)
                diffs.append(attrs_diff)
        else:
            changed = True
    return UserResult(changed=changed, diff=diffs)


def main():
    module = AnsibleModule(
        argument_spec={
            "header": {"type": "str", "default": DEFAULT_HEADER},
            "users": {
                "type": "list",
                "elements": "dict",
                "required": True,
                "options": {
                    "user": {"type": "str", "required": True},
                    "keys": {"type": "list", "elements": "str", "required": True},
                },
            }
        },
        supports_check_mode=True,
    )
    try:
        users = [UserKeys(**entry) for entry in module.params["users"]]
        plans = prepare_users(users, module.params["header"])
        changed = False
        diffs = []
        for plan in plans:
            result = manage_user(module, plan)
            changed = result.changed or changed
            diffs.extend(result.diff)
        module.exit_json(changed=changed, **({"diff": diffs} if module._diff else {}))
    except (OSError, KeyError, ValueError, binascii.Error) as error:
        module.fail_json(msg=str(error))


if __name__ == "__main__":
    main()
