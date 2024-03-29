#!/usr/bin/env python3

"""Parse ed25519 SSH keys.

From the fgtk
* <https://github.com/mk-fg/fgtk/blob/master/ssh-keyparse>
* <https://blog.fraggod.net/2015/09/04/parsing-openssh-ed25519-keys-for-fun-and-profit.html>
"""


import itertools as it, operator as op, functools as ft
import os, sys, io, re, struct, tempfile, hashlib, base64, binascii
import subprocess as sp, pathlib as pl


class SSHKeyError(Exception):
    pass


def ssh_key_parse(path, patch_sk=None, decrypt=True):
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=path.name + ".") as tmp:
        try:
            tmp.write(path.read_bytes())
            tmp.flush()

            if decrypt:
                cmd = ["ssh-keygen", "-p", "-P", "", "-N", "", "-f", tmp.name]
                p = sp.run(cmd, encoding="utf-8", errors="replace", stdin=sp.DEVNULL, stdout=sp.PIPE, stderr=sp.PIPE)
                stdout, stderr = p.stdout.splitlines(), p.stderr.splitlines()
                err = p.returncode

                if err:
                    if stdout:
                        print("\n".join(stdout), file=sys.stderr)
                    key_enc = False
                    for line in stderr:
                        if re.search(
                            r"^Failed to load key .*:" r" incorrect passphrase supplied to decrypt private key$", line
                        ):
                            key_enc = True
                        else:
                            print(line, file=sys.stderr)
                    if key_enc:
                        print("WARNING:")
                        print(
                            "WARNING: !!! ssh key will be decrypted"
                            f" (via ssh-keygen) to a temporary file {tmp.name!r} in the next step !!!"
                        )
                        print(
                            "WARNING: DO NOT enter key passphrase" " and ABORT operation (^C) if that is undesirable."
                        )
                        print("WARNING:")
                        cmd = ["ssh-keygen", "-p", "-N", "", "-f", tmp.name]
                        err, p = None, sp.run(
                            cmd, check=True, encoding="utf-8", errors="replace", stdout=sp.PIPE, stderr=sp.PIPE
                        )
                        stdout, stderr = p.stdout.splitlines(), p.stderr.splitlines()

                if err or "Your identification has been saved with the new passphrase." not in stdout:
                    for lines in stdout, stderr:
                        print("\n".join(lines).decode(), file=sys.stderr)
                    raise SSHKeyError(
                        (
                            "ssh-keygen failed to process key {}," " see stderr output above for details, command: {}"
                        ).format(path, " ".join(cmd))
                    )

            res = _ssh_key_parse(path, tmp, patch_sk)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    return res


def _ssh_key_parse(path, tmp, patch_sk=None):
    # See PROTOCOL.key and sshkey.c in openssh sources
    tmp.seek(0)
    lines, key, done = tmp.read().decode().splitlines(), list(), False
    for line in lines:
        if line == "-----END OPENSSH PRIVATE KEY-----":
            done = True
        if key and not done:
            key.append(line)
        if line == "-----BEGIN OPENSSH PRIVATE KEY-----":
            if done:
                raise SSHKeyError("More than one" f" private key detected in file, aborting: {path!r}")
            assert not key
            key.append("")
    if not done:
        raise SSHKeyError(f"Incomplete or missing key in file: {path!r}")
    key_bytes = base64.standard_b64decode("".join(key))
    key_str_wrap = max(map(len, key))
    key_struct = io.BytesIO(key_bytes)

    def key_read_bytes(src=None):
        if src is None:
            src = key
        (n,) = struct.unpack(">I", src.read(4))
        return src.read(n)

    def key_write_bytes(s, pos=None, dst=None):
        if dst is None:
            dst = key
        if pos:
            dst.seek(pos)
        dst.write(struct.pack(">I", len(s)))
        return dst.write(s)

    def key_assert(chk, err, *fmt_args, **fmt_kws):
        if chk:
            return
        if fmt_args or fmt_kws:
            err = err.format(*fmt_args, **fmt_kws)
        err += f" [key file: {path!r}, decoded: {key_bytes!r}]"
        raise SSHKeyError(err)

    def key_assert_read(field, val, fixed=False):
        pos, chk = key.tell(), key.read(len(val)) if fixed else key_read_bytes()
        key_assert(
            chk == val, "Failed to match key field" " {!r} (offset: {}) - expected {!r} got {!r}", field, pos, val, chk
        )

    key = key_struct
    key_assert_read("AUTH_MAGIC", b"openssh-key-v1\0", True)
    key_assert_read("ciphername", b"none")
    key_assert_read("kdfname", b"none")
    key_assert_read("kdfoptions", b"")
    (pubkey_count,), pubkeys, pos_pk1 = struct.unpack(">I", key.read(4)), list(), list()
    for n in range(pubkey_count):
        pos_line = key.tell()
        line = key_read_bytes()
        key_assert(line, "Empty public key #{}", n)
        line = io.BytesIO(line)
        key_t = key_read_bytes(line).decode()
        key_assert(key_t == "ssh-ed25519", "Unsupported pubkey type: {!r}", key_t)
        pos_pk1.append(pos_line + 4 + line.tell())
        ed25519_pk = key_read_bytes(line)
        line = line.read()
        key_assert(not line, "Garbage data after pubkey: {!r}", line)
        pubkeys.append(ed25519_pk)
    pos_privkey_struct = key.tell()
    privkey_struct = io.BytesIO(key_read_bytes())
    pos, tail = key.tell(), key.read()
    key_assert(not tail, "Garbage data after private key (offset: {}): {!r}", pos, tail)

    key = privkey_struct
    n1, n2 = struct.unpack(">II", key.read(8))
    key_assert(n1 == n2, "checkint values mismatch in private key spec: {!r} != {!r}", n1, n2)
    key_t = key_read_bytes().decode()
    key_assert(key_t == "ssh-ed25519", "Unsupported key type: {!r}", key_t)
    pos_pk2 = key.tell()
    ed25519_pk = key_read_bytes()
    pos_pk1_idx = list(n for n, pk in enumerate(pubkeys) if pk == ed25519_pk)
    key_assert(pos_pk1_idx, "Pubkey mismatch - {!r} not in {}", ed25519_pk, pubkeys)
    pos_sk = key.tell()
    ed25519_sk = key_read_bytes()
    key_assert(
        len(ed25519_pk) == 32 and len(ed25519_sk) == 64,
        "Key length mismatch: {}/{} != 32/64",
        len(ed25519_pk),
        len(ed25519_sk),
    )
    comment = key_read_bytes()
    padding = key.read()
    padding, padding_chk = bytearray(padding), bytearray(range(1, len(padding) + 1))
    key_assert(padding == padding_chk, "Invalid padding: {!r} != {!r}", padding, padding_chk)

    if patch_sk:
        assert len(patch_sk) == 64
        key_write_bytes(patch_sk[32:], pos_pk2)
        key_write_bytes(patch_sk, pos_sk)
        key_write_bytes(key.getvalue(), pos_privkey_struct, key_struct)
        for n in pos_pk1_idx:
            key_write_bytes(patch_sk[32:], pos_pk1[n], key_struct)
        key_bytes = key_struct.getvalue()

        tmp.seek(0)
        tmp.truncate()
        tmp.write(b"-----BEGIN OPENSSH PRIVATE KEY-----\n")
        tmp.write(b64encode(key_bytes, line_len=key_str_wrap).encode())
        tmp.write(b"-----END OPENSSH PRIVATE KEY-----\n")
        tmp.flush()
        os.rename(tmp.name, path)

    return ed25519_sk


def ed25519_pubkey_from_seed(sk):
    # Crypto code here is py3 version of http://ed25519.cr.yp.to/python/ed25519.py

    b = 256
    q = 2**255 - 19
    l = 2**252 + 27742317777372353535851937790883648493

    def H(m):
        return hashlib.sha512(m).digest()

    def expmod(b, e, m):
        if e == 0:
            return 1
        t = expmod(b, e // 2, m) ** 2 % m
        if e & 1:
            t = (t * b) % m
        return t

    def inv(x):
        return expmod(x, q - 2, q)

    d = -121665 * inv(121666)
    I = expmod(2, (q - 1) // 4, q)

    def xrecover(y):
        xx = (y * y - 1) * inv(d * y * y + 1)
        x = expmod(xx, (q + 3) // 8, q)
        if (x * x - xx) % q != 0:
            x = (x * I) % q
        if x % 2 != 0:
            x = q - x
        return x

    By = 4 * inv(5)
    Bx = xrecover(By)
    B = [Bx % q, By % q]

    def edwards(P, Q):
        x1 = P[0]
        y1 = P[1]
        x2 = Q[0]
        y2 = Q[1]
        x3 = (x1 * y2 + x2 * y1) * inv(1 + d * x1 * x2 * y1 * y2)
        y3 = (y1 * y2 + x1 * x2) * inv(1 - d * x1 * x2 * y1 * y2)
        return [x3 % q, y3 % q]

    def scalarmult(P, e):
        if e == 0:
            return [0, 1]
        Q = scalarmult(P, e // 2)
        Q = edwards(Q, Q)
        if e & 1:
            Q = edwards(Q, P)
        return Q

    def encodeint(y):
        bits = [(y >> i) & 1 for i in range(b)]
        return bytes(sum([bits[i * 8 + j] << j for j in range(8)]) for i in range(b // 8))

    def encodepoint(P):
        x = P[0]
        y = P[1]
        bits = [(y >> i) & 1 for i in range(b - 1)] + [x & 1]
        return bytes(sum([bits[i * 8 + j] << j for j in range(8)]) for i in range(b // 8))

    def bit(h, i):
        return (h[i // 8] >> (i % 8)) & 1

    def publickey(sk):
        h = H(sk)
        a = 2 ** (b - 2) + sum(2**i * bit(h, i) for i in range(3, b - 2))
        A = scalarmult(B, a)
        return encodepoint(A)

    def Hint(m):
        h = H(m)
        return sum(2**i * bit(h, i) for i in range(2 * b))

    def signature(m, sk, pk):
        h = H(sk)
        a = 2 ** (b - 2) + sum(2**i * bit(h, i) for i in range(3, b - 2))
        r = Hint(bytes(h[i] for i in range(b // 8, b // 4)) + m)
        R = scalarmult(B, r)
        S = (r + Hint(encodepoint(R) + pk + m) * a) % l
        return encodepoint(R) + encodeint(S)

    def isoncurve(P):
        x = P[0]
        y = P[1]
        return (-x * x + y * y - 1 - d * x * x * y * y) % q == 0

    def decodeint(s):
        return sum(2**i * bit(s, i) for i in range(0, b))

    def decodepoint(s):
        y = sum(2**i * bit(s, i) for i in range(0, b - 1))
        x = xrecover(y)
        if x & 1 != bit(s, b - 1):
            x = q - x
        P = [x, y]
        if not isoncurve(P):
            raise Exception("decoding point that is not on curve")
        return P

    def checkvalid(s, m, pk):
        if len(s) != b // 4:
            raise Exception("signature length is wrong")
        if len(pk) != b // 8:
            raise Exception("public-key length is wrong")
        R = decodepoint(s[0 : b // 8])
        A = decodepoint(pk)
        S = decodeint(s[b // 8 : b // 4])
        h = Hint(encodepoint(R) + pk + m)
        if scalarmult(B, S) != edwards(R, scalarmult(A, h)):
            raise Exception("signature does not pass verification")

    pk = publickey(sk)
    # m = b'test'
    # s = signature(m, sk, pk)
    # checkvalid(s, m, pk)
    return pk


it_adjacent = lambda seq, n: it.zip_longest(*([iter(seq)] * n))
_b32_abcs = dict(
    zip(
        # Python base32 - "Table 3: The Base 32 Alphabet" from RFC3548
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567",
        # Crockford's base32 - http://www.crockford.com/wrmg/base32.html
        "0123456789ABCDEFGHJKMNPQRSTVWXYZ",
    )
)
_b32_abcs["="] = ""


def b32encode(v, chunk=4, _trans=str.maketrans(_b32_abcs), _check="".join(_b32_abcs.values()) + "*~$=U"):
    chksum = 0
    for c in bytearray(v):
        chksum = chksum << 8 | c
    res = "-".join(
        "".join(filter(None, s)) for s in it_adjacent(base64.b32encode(v).decode().strip().translate(_trans), chunk)
    )
    return "{}-{}".format(res, _check[chksum % 37].lower())


def b64decode(data):
    return base64.standard_b64decode(data.replace("-", "+").replace("_", "/"))


def b64encode(data, urlsafe=False, line_len=None):
    enc = base64.standard_b64encode if not urlsafe else base64.urlsafe_b64encode
    data = enc(data).decode()
    if line_len:
        lines = list("".join(filter(None, line)) for line in it_adjacent(data, line_len))
        data = "\n".join(lines + [""])
    return data


def main(args=None):
    path_default = "~/.ssh/id_ed25519"
    path_sys = "/etc/ssh/ssh_host_ed25519_key"

    import argparse

    parser = argparse.ArgumentParser(
        description="OpenSSH ed25519 key processing tool."
        " Prints urlsafe-base64-encoded (by default) 32-byte"
        " secret ed25519 key without any extra wrapping."
    )

    group = parser.add_argument_group("Key specification and operation mode")

    group.add_argument("path", nargs="?", help=f"Path to ssh private key to process. Default: {path_default}")

    group.add_argument(
        "-s",
        "--expand-seed",
        metavar="b64-encoded-32b-key-seed",
        help="Derive expanded 64-byte key from"
        " specified base64-encoded 32-byte ed25519 seed value."
        ' "path" argument will be ignored if this option is specified.',
    )
    group.add_argument(
        "-d",
        "--patch-key",
        metavar="b64-encoded-32b-key-seed",
        help="Replace key specified by path argument with one derived from ed25519 seed value."
        " Few bits of (mostly irrelevant) openssh"
        " non-key-material metadata will be left in the keyfile as-is."
        " NOTE: THIS WILL DESTROY OLD SSH PRIVATE KEY IN THAT FILE!!!",
    )

    group.add_argument(
        "-y",
        "--system",
        action="store_true",
        help='Dont use "path" argument and parse sshd key from /etc/ssh.'
        f" Basically a shorthand for specifying {path_sys} as path arg.",
    )
    group.add_argument(
        "-u",
        "--public",
        action="store_true",
        help="Read and print public key from .pub file alongside private one."
        " This is purely a convenience option to get both backup"
        " of private key and public key for it to paste somewhere.",
    )

    group = parser.add_argument_group("Processing options")
    group.add_argument(
        "-p",
        "--pbkdf2",
        nargs="?",
        metavar="format",
        const="{salt}{res}",
        help="Use one-way PBKDF2 transformation on the raw key."
        " Optional argument allows to control how result"
        ' ("res" format key) and salt ("salt" key) will be combined in the output,'
        ' default: "{salt}{res}".',
    )
    group.add_argument(
        "--pbkdf2-opts",
        nargs="?",
        metavar="algo/rounds/salt-bytes[/salt]",
        default="sha256/500000/6",
        help='PBKDF2 parameters in "algo/rounds/salt-bytes[/salt]" format.'
        ' "salt-bytes" value is only used if salt'
        " value is not specified explicitly, otherwise ignored."
        ' "salt" will be read from /dev/urandom, if omitted. Default: %(default)s',
    )
    group.add_argument(
        "-t",
        "--truncate",
        metavar="bytes",
        type=int,
        help="Truncate result to specified number of bytes before encoding." " Default is to never truncate anything.",
    )

    group = parser.add_argument_group("Encoding options")
    group.add_argument(
        "-b",
        "--base64",
        action="store_true",
        help="Encode result using *urlsafe*" " (aka filesystem-safe) base64 encoding. This is the default.",
    )
    group.add_argument(
        "--base64-alt",
        action="store_true",
        help="Encode result using base64 with standard alphabet (has + and / in it).",
    )
    group.add_argument("-x", "--hex", action="store_true", help='Encode result using "hex" encoding (0-9 + a-f).')
    group.add_argument(
        "-c",
        "--base32",
        action="store_true",
        help="Encode result using readability-oriented Douglas Crockford's Base32 encoding."
        " All visually-confusing symbols (e.g. 1 and l, 0 and O, etc)"
        " in this encoding are interchangeable and case does not matter,"
        " hence easier to read for humans. Check symbol gets added at the end."
        " Format description: http://www.crockford.com/wrmg/base32.html",
    )
    group.add_argument("--base32-nodashes", action="store_true", help="Same as --base32, but without dashes.")
    group.add_argument(
        "-r", "--raw", action="store_true", help="Do not encode result in any way, print raw bytes with nothing extra."
    )

    opts = parser.parse_args(sys.argv[1:] if args is None else args)

    path = opts.path
    if opts.system:
        if path:
            parser.error("--system option cannot be used together with path.")
        path = path_sys
    if not path:
        path = path_default
    path = pl.Path(path).expanduser()

    seed = opts.expand_seed or opts.patch_key
    if seed:
        if opts.public:
            parser.error("--public option cannot be used together with --expand-seed/--patch-key.")
        res = b64decode(seed)
        res = res + ed25519_pubkey_from_seed(res)
        if opts.patch_key:
            ssh_key_parse(path, patch_sk=res)
            if not opts.expand_seed:
                return

    else:
        if not path.exists():
            parser.error(f"Key path does not exists: {path!r}")
        res = ssh_key_parse(path)
        # assert res == res[:32] + ed25519_pubkey_from_seed(res[:32])
        res = res[:32]

    if opts.pbkdf2:
        algo, rounds, salt = opts.pbkdf2_opts.split("/", 2)
        try:
            salt_len, salt = salt.split("/", 1)
        except ValueError:
            salt = os.urandom(int(salt))
        res = hashlib.pbkdf2_hmac(algo, res, salt, int(rounds))

    if opts.truncate:
        res = res[: opts.truncate]

    enc_sum = sum(map(bool, [opts.base64, opts.hex, opts.base32, opts.base32_nodashes, opts.raw]))
    if enc_sum > 1:
        parser.error("At most one encoding option can be used at the same time.")
    if not enc_sum or opts.base64:
        res = b64encode(res, urlsafe=True)
    elif opts.base64_alt:
        res = b64encode(res, urlsafe=False)
    elif opts.hex:
        res = binascii.b2a_hex(res).decode()
    elif opts.base32:
        res = b32encode(res)
    elif opts.base32_nodashes:
        res = b32encode(res).replace("-", "")

    if opts.raw:
        bin_stdout = open(sys.stdout.fileno(), "wb")
        if opts.public:
            parser.error("--public option cannot be used together with --raw.")
        bin_stdout.write(res)
    else:
        print(res)
    if opts.public:
        print(path.parent / (path.name + ".pub").read_text().strip())


if __name__ == "__main__":
    sys.exit(main())
