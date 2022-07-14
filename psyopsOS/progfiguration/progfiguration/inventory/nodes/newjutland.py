"""My synergy controller

Untested so far
"""

from progfiguration.inventory.invhelpers import Bunch


# The private key, encrypted by age
# FRom .synergy/SSL/Synergy.pem
synergy_private_key = """\
-----BEGIN AGE ENCRYPTED FILE-----
YWdlLWVuY3J5cHRpb24ub3JnL3YxCi0+IFgyNTUxOSBXOVE5NEc5K0FCZHFDaFdY
NUhFZjY4UnN5a0g5TitIZXB5Q2p5b0VMM0NFCk9RMWd4bkxNZFVYdmZmZVdPN080
Q2kzb1ZxS2RzVHc1cTJORDNGVTU0MFkKLS0tIE1SZS8vTmFueStIRFN5cTRwT3du
ejdYa1UvTk4zdHRHc3FXS0toWEg5ZHMK01WnlNINY11OtyjsgSzvWIkMfGUGFUOT
lUIg8BqtnXzf57qTNG2s2MENV4rGltkFymfZKe9BY6+KSEcVYIfNEBIQcUdKVvbj
CaFCp9S1AYPeNrI433946xSRZSW43MOg+Snlq807GPNMhREV1XZBNSvDZ3BzW+ua
43PBpeVtHK1JHsG1yLO0W3NqbyeGff5I8++CwqqiLdCSxddqGF6JxRb1L//Tt1Jl
A4/pSfYLa5PmXA7ZVpUSkORUbfqS7BVk3ZB5OKxTvuTkrh3W7wM+K5JS/5lVWOzi
726zi/CXNLWhz3+fBRH4Lg+uu7iQx0GvoKgh2b6h5VfyuNZc8wyLX75BpHeDuyVR
oGZ9frMN/4fNMX4IE0ctaFWfWLiK4cKaijjh0EKdTc+wUMRyc158nwvy+jm2/z/u
VVDjZTsuBccpK3F6z8zFswvkw+PJgF06J/5SEzTQiJavCGW1dCEPbrU2ecqjEV1c
YsihCSdsvNUsQRm/6nXxsAw4G07IKqoPcXRNYHIlkIwGuUW/C7fYwWFyRyimI9bc
Y0WAy19lQcCQFsBpfvTqI/n+N4zy5sebGDq86DON6npHmvlsZjNJBxizhGGxGZjV
cZghDouvI3fazCX3oiLptnmxP6J6gNgWicyJuiaK5ZMc2E4gnG1QOBV61rkVc9ru
MBLJ6UgYiuGiF5Th581hjeuqQ77myd0HkXmWGbnjeUlS2RSBV8YbEUUx9zXmIZHS
eegVmjlQK1CySzXrE753Cm8L5VY//XI0C1GsVeXrgOGIGXhjq6MnjJHSv/vNPopo
/Tt++ZabUTyfcWyhfS2/3nfSAeSM/l6a6lC0EdI1W1BHK2HBjdtr0fIgeJJtTcVL
wmbAw6mDuUORapG1iF2nzg1K3hgYHKbNmTguvdo0zCmMjyCe4cdP0JCGl+Lv6nBN
9wgY8ZYYmnFqlUDb5ofk1cjrG2vF3aaRLY9MK/GCpctENxCwNpx6I8AnBCKMjW+B
DQSw+bY5gfTxkFSAwiV+rKlp1x9p5U1GxCxW9a0WEV7KIFVSH+UiVoA1f+xVMltE
AEIiUYDSmqvQaCADb7hFB00kpvVR22x2ft/Axr7vARZew96GKGIot+j9pGtttJCz
hqWtLzFLcH/pGHE0Ojegi0j0d/z98hOZWQ/XBkvCVixpeXbKdMzW7v+seMjror0I
J5MKPoz3Sbs9DRwc0Zttwsk1NVrnyXpZYS1EFYcCHSviDhVBH90BGTecT9vHEOH+
OkZBUv2xAM5LorEmW+VogjcG1f8/Z2DI5/PVytIOrLTEK20JkcK1ovBagYWN+oGC
SwJIk84BCiDZjt2dSdCOc1AYcbllR84W88mTEyvsZYZAyDsxD5WQ6B2MPvuvBiOD
nQLmJOOWKIHkJpCp7OXnCpiFdDPB+Mugk1fc33yjy/OENC9LtYM/VQrd3yYoZSOM
3fZNCum6e2r0Hxx2WZptCI1z73NU56qSIIUVnDydFrHLTsZSwv74/j8YyZFCylcB
wL2V4+PsxFTyI+ZHzRopqwB+nG8t0TTANhCJwXFeuHCNvF8KbCUYWantbDVdcHz7
iNZan9w98ETtAc0hSWulT63Bs9CxfQ3X+14ppaYXtXdyLSqa8yZPtyInEqSUoGHS
vcTyIsBZzSujqFZ/r0DuIzdp/lg1ZuiZ053W+d9rR1ef5iwBtDbWFVCMwLJdPleI
/Wv2+0A/7mSaa1exxnO8H72OqmqdeoxBHcGgPcNf00YHDn7vB7vpj3DRUpldJEEw
kdAmCNyGujhHsG7qSQMB0ee1ZRLEoAe+gjZFUkbEbd3cUpRjOIEiomPvADto4qs5
4wcaGgT982Xjf3l/6JNyOk9VXefNp0aZuy2wRuoWtLIDnfVecl1ccpSPQzvDFgFn
Pk74H7vqQxXWEJaSP8GRrbQqfbV26tIcdQRuXgh1vF3B54Yhq5EsZjH0IeQtVb1L
rn3aZiMkSDKDPhXADFq3z7XOS9pQ+Xh4RabtVN3HUdRQyFpcBc/U/vTnH8O3b6+W
f9VhHCTFUaUXcE8CWXnb8me/spmhQIRqy9ZpvwYjoNZ8b4PNlrKpSNEG3wUSUkHy
vTjSu/TkQaLu1YoLiTwet5hm9NSrYVGVX6FQEiXQi/AM/ycdhpRcfdO+v0mMVPlR
XbgppOtNk5sLeSBL0b9iPLsPPextqLSp/P+YTA30I0lWjV5XJydLiM6h2dSq4Kqs
DSP6+g8KZDUxpcAEvbCEIgrNHSxzFosusEVUJuaSknBjlcSxQOYmq4jw4HBg/sah
4PofESBsZ5QPz6QV4C/PAsCy308WC1dLbKSoALgDN14=
-----END AGE ENCRYPTED FILE-----
"""

# The public key, not encrypted
# From .synergy/SSL/Synergy.pem
synergy_public_key = """\
-----BEGIN CERTIFICATE-----
MIIDBTCCAe2gAwIBAgIUab0g9ynuMqUSrcAM2yOfDTJoXCowDQYJKoZIhvcNAQEL
BQAwEjEQMA4GA1UEAwwHU3luZXJneTAeFw0yMDExMTEyMjU2MDhaFw0yMTExMTEy
MjU2MDhaMBIxEDAOBgNVBAMMB1N5bmVyZ3kwggEiMA0GCSqGSIb3DQEBAQUAA4IB
DwAwggEKAoIBAQDAvsHTCt9pL+TpzM1LMhVO6OL0Xa/krhjXmOHfeeV08v2X6j7h
bCvo+tdtcnl2iUc9/+4VZx4hGVhKDfQnBoKM2htxWLfqklN06YlFH/Oq8o4Ak9tl
iECpzfOW8TeEZ8wPPMiNAVRe+jhc4HxzobR1qc7cWp9yt4T0aoyCnpYRYubHtIUo
f5ghOAcm/vf58m44Q7RK9V/Jk5joMaE4QQzmyEydXLqPSr9InfV5nK9IgYkjrSci
TJn/lMC/vscHKV2SFcN/VYz11tUCbM2CdJ56IIQYgEQXCueJ5KpuhvKJOo1Zv8oX
uSWTB0UcRzgKUiA6i/r+5FWXb+OlAlyQuoNRAgMBAAGjUzBRMB0GA1UdDgQWBBTh
L5rfL1aJKUkCIt2KnI/QiwAPwDAfBgNVHSMEGDAWgBThL5rfL1aJKUkCIt2KnI/Q
iwAPwDAPBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQAI5IfCcFkx
AtocSVfhf33+aeBxZvVZpEkbQBUkenzSj8MBWVKUQj9O589fDSCfdpvOnIkoAQnb
ZxajPX6rE3bdKaFY5NC9hfeElGnyZ5YYcvovp6IYL9DehP9D4u2gaUMFuC0ePRm3
O8Lz3UQzb6SNTyLbfqJIoWP7ffFsVFVmn6/ehvoyXuhbzFk/KgkDGvkKqcw3Zj/5
r+kQEHIdBVuCaRveUkmA+auC2D3Ts0Cem7+8r9TVga3d5JCJUmeeWyRrBTrA5JU+
kk2ukIeBcqKQt5++IlupKw0WuPXL29rHEhgd8Tcx0RBYob3cHmvG9WljgkEdc04A
/2PB+ogTPJw8
-----END CERTIFICATE-----
"""


# The contents of .synergy/SSL/Fingerprints/Local.txt
synergy_fingerprints_local = """\
10:A7:6C:8B:1E:13:70:26:CC:51:7E:D7:BA:C7:54:A5:75:0D:61:0A:31:50:6A:5F:61:98:04:B7:F7:F6:CD:65
"""


# An encrypted serial key for Synergy
synergy_serial_key = """\
-----BEGIN AGE ENCRYPTED FILE-----
YWdlLWVuY3J5cHRpb24ub3JnL3YxCi0+IFgyNTUxOSBlaFNLZUtMdmQyZjhnd2J0
dEZXYWhLQndGb012aEgyamIwNWFUa0NLb2dZCmdEdGw3eC9vZkxUU0NlUTJaZVhN
Q1lvZG9WRk51SGUzdThYclA5bzRjcG8KLS0tIG5Jcm9oTDZ3dUExdGRRYVhlcUpU
cnJVZHd6Y20zRXE5eDdaeU5sTzlVUzgKjI/yFlS8ba0S1OPxqEPuTFbik1JP5+sP
uoSeZsuXUhUGJJVvSWtXj4hO/GX9IhfihvS2lvsCyuywnI0TZQRBHFDj5IEINDE0
h2dHwnEJqDd2JgPb4+3gIrZTUpKTOdMvOfUVem053Yk=
-----END AGE ENCRYPTED FILE-----
"""


node = Bunch(
    notes="",
    motd=Bunch(
        flavor="NEW JUTLAND: The final destination of all train graffiti. The glyphs slither down from their cars and become three-dimensional aberrations.",
    ),
    pubkey="age12sdqyt4pj3luus62qklyusj4ykk5sr6wr44jhtv0q84suzg5n9vqgkhru0",
    roles=Bunch(
        datadisk={
            "underlying_device": "/dev/mmcblk1",
            "wipe_after_mounting": ["overlays/var-lib-flatpak/"],
        },
        synergycontroller={
            "secret_synergy_priv_key": synergy_private_key,
            "secret_synergy_serial_key": synergy_serial_key,
            "synergy_pub_key": synergy_public_key,
            "synergy_fingerprints_local": synergy_fingerprints_local,
            "synergy_server_screenname": "newjutland",
        },
    ),
    nics={
        "psy0": "00:07:32:4c:eb:9a",
    },
    serial="",
)
