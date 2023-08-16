"""My synergy controller

Untested so far
"""

from progfiguration.age import AgeSecretReference
from progfiguration.inventory.nodes import InventoryNode

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


node = InventoryNode(
    address="newjutland.home.micahrl.com",
    user="root",
    age_pubkey="age12sdqyt4pj3luus62qklyusj4ykk5sr6wr44jhtv0q84suzg5n9vqgkhru0",
    ssh_host_fingerprint="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMV71LKt9qu15k32QcuQFZWWO/bmEEbZD5W3a43i5mZH",
    sitedata=dict(
        flavortext="NEW JUTLAND: The final destination of all train graffiti. The glyphs slither down from their cars and become three-dimensional aberrations.",
        psy0mac="00:07:32:4c:eb:9a",
        serial="",
    ),
    roles=dict(
        datadisk_v1={
            "underlying_device": "/dev/sda",
            "wipe_after_mounting": ["overlays/var-lib-flatpak/"],
            "ramoffload": True,
        },
        synergycontroller={
            "synergy_priv_key": AgeSecretReference("synergy_private_key"),
            "synergy_serial_key": AgeSecretReference("synergy_serial_key"),
            "synergy_pub_key": synergy_public_key,
            "synergy_fingerprints_local": synergy_fingerprints_local,
            "synergy_server_screenname": "newjutland",
            "github_deploy_key": AgeSecretReference("synergist_github_deploy_key"),
        },
    ),
)
