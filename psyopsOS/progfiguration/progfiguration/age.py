"""A wrapper for the age binary to encrypt and decrypt secret values"""

import datetime
import subprocess
from typing import List


class AgeKey:
    def __init__(self, secret: str, public: str, created: datetime.datetime):
        self.secret = secret
        self.public = public
        self.created = created

    @classmethod
    def from_output(cls, output: str) -> "AgeKey":
        example_stdout = """
            # created: 2022-09-28T16:01:22-05:00
            # public key: age14e42u048nehghjj3ch9mmnkdh4nsujn774klqxn02mznppx3gflsuj6y5m
            AGE-SECRET-KEY-1ASKGXED4DVGUH7SA50DHE2UHAYQ00PV87N2RQ5J5S6AUN9MLNSGQ3TKFGJ
        """
        outlines = output.split("\n")
        created = datetime.datetime.fromisoformat(outlines[0][11:])
        public = outlines[1][14:]
        secret = outlines[2]
        return cls(secret, public, created)

    @classmethod
    def generate(cls) -> "AgeKey":
        result = subprocess.run(["age-keygen"], check=True, capture_output=True)
        return cls.from_output(result.stdout)

    @classmethod
    def from_file(cls, path: str) -> "AgeKey":
        with open(path) as fp:
            content = fp.read()
        return cls.from_output(content)


def encrypt(value: str, pubkeys: List[str]):
    """Encrypt a value to a list of public age keys"""
    age_cmd = ["age", "--armor"]
    for pubkey in pubkeys:
        age_cmd.append("--recipient")
        age_cmd.append(pubkey)
    proc = subprocess.run(age_cmd, input=value.encode(), check=True, capture_output=True)
    return proc.stdout


def decrypt(value: str, privkey_path: str):
    """Decrypt an encrypted age value"""
    proc = subprocess.run(
        ["age", "--decrypt", "--identity", privkey_path],
        input=value.encode(),
        check=True,
        capture_output=True,
    )
    return proc.stdout.decode()
