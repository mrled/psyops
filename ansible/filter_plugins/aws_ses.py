#!/usr/bin/python3
"""Ansible filter plugin for AWS SES SMTP credential derivation.

Usage in a playbook:

    smtp_password: "{{ iam_secret_access_key | ses_smtp_password(region) }}"
"""

import base64
import hashlib
import hmac


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def ses_smtp_password(secret_access_key: str, region: str) -> str:
    if not secret_access_key:
        raise ValueError("secret_access_key must not be empty")
    if not region:
        raise ValueError("region must not be empty")
    signature = _sign(("AWS4" + secret_access_key).encode("utf-8"), "11111111")
    signature = _sign(signature, region)
    signature = _sign(signature, "ses")
    signature = _sign(signature, "aws4_request")
    signature = _sign(signature, "SendRawEmail")
    return base64.b64encode(bytes([0x04]) + signature).decode("utf-8")


class FilterModule(object):
    def filters(self):
        return {
            "ses_smtp_password": ses_smtp_password,
        }
