from progfiguration.inventory.nodes import InventoryNode
from progfiguration.sitehelpers.agesecrets import AgeSecretReference

psyops_seedboxk8s_flux_deploy_id_pub = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILt/A31ST7QW45mG7MBJSmHg3483YCIIVHbNuNPUgXEn"
)

seedboxk8s_ca_crt = """-----BEGIN CERTIFICATE-----
MIIFJTCCAw2gAwIBAgIULOK3Xyts43aSvGEOsea39hHncA4wDQYJKoZIhvcNAQEL
BQAwITEfMB0GA1UEAwwWU2VlZGJveEs4cyBJbnRlcm5hbCBDQTAgFw0yNDA1MTYw
MjA3MTFaGA8yMTI0MDQyMjAyMDcxMVowITEfMB0GA1UEAwwWU2VlZGJveEs4cyBJ
bnRlcm5hbCBDQTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAKJ5p4zF
NWJ7qUKRc8dwO6m55NwhXxEUj8H+4mype/3Zsnc+HPohOdHzw4v/7Z24aXk5S1RY
wTF12ouH03uG1PjUU/QpixW7vOvKnJjh1huhMr5vhjFFiaA+DCKTH60kruBTpaH5
/620oZQAkUugZp4qzZoygXECOLvNp7+tfm9nSrOQYJcOyDopZdcSMbHA5uPblKl+
IR+UE0A7cMiR2IVHpgtfTQpXNZzHHG8k2ULi2ykrofFLPCx5i1C0p9Bp+ZupjQyD
mO0KZx0bwqmEwo75TH7Y/4o6epSkR2ryX2iBYa1G6rwnUG3Yt5jfnXWCQtbMMSv/
klEAdu8hoANv7gPBZ/Cf6w2etQmmgDPaLMTOb/PRLRdLJPWhAB8ZRsvnWyozM2qE
2FZ4YSaQCX/ZiCGZ443NLwtFABYrj6GY/NhwtmOpGacU/h/mQqAc4NAEfHyxhVTZ
wiAvjJk/5F9mmRw6LdejHHUgL1rSS9A3N3kvNI1IaEX/JUREEawbt5VHBfZdl69O
wKW6ez9AoO5ctDqdbPWmtEuLMbGh1vZkErVhYxgMQymc0qxUKuzHdKCQFfl3DmnH
bUDv/pg9QprjD9/VXp5OUZ87aqNVYhWRw1GTf70oPaYR/7ArRnnu+wTVhsufYynO
S2xcQjJkb6wCJPSaHNFZT4907TzJSTJFzzxRAgMBAAGjUzBRMB0GA1UdDgQWBBQ8
TmSjq1knwh5UGLjL5HHKDW960zAfBgNVHSMEGDAWgBQ8TmSjq1knwh5UGLjL5HHK
DW960zAPBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4ICAQAf7chK8MJ9
qRb7/v2QOfVILi3aCd1wRgp42WtfCyKXFMJMHdcCFAjFeUlrViQwjnh9R2SlvGSE
XjzuJxItNVbFHCq/BqMnHLTnSr9lHF4eeBwoCiDNqz7fqs9+qGIRxmaf5M5WSxQn
5LV1A0JbRDQY/pcA/3ilVbMmz434COueNco13Zrk+Wb6ZLT1dg5mLj3SG7ykLQqQ
w75KJb6/ahTiEaRdw5D5aaSMQxkVUU745yvWgQXUYvlR+56lKkwLmDRlLSXtm5L2
Fol0hGfYULIzB/8tUhcGldf4qJ1KoaodcdeHU7D7ybrjp7eV+BWdr3RoCIO8eaAw
LjYHUidnTARt7dIdrVKvaje2sadDisAnX8vZrcQQSJtaTaWv9EX7nV+jOQfIM5lR
WsBj2ie15rcCa0weud1Omz/oyoABT0lYvh4QhhF/kIJGscw/O3Nq3O09mxKwfiWp
BSTgGS9KH13h7HYnOMu2Fp5dbiPzzAPHHq2wrTODjL4JwXKfJryVwmqhqiWE2vPk
w/xNTa7N0SZPuRfHDI9nTZI4aoqo+J1/f+aIlOGWrIDkuu4QOKJqrqg7Cu6gBcWT
6b0w7C8sTxz5FCVh3auJ7XxDRArKRGzOiQgJHsPhbZ/lSuIoZn+EyGLpJh+JgOgd
mLavGRPXiplyFwJPvAXNzzGDHUa27rgkmg==
-----END CERTIFICATE-----
"""

node = InventoryNode(
    address="tagasaw.home.micahrl.com",
    user="root",
    ssh_host_fingerprint="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBnflMza3MO/ECgF8VUjm5lm1p+Q7TIDPKl4niXGNPMk",
    python="/usr/bin/python3.11",
    sitedata=dict(
        notes="",
        flavortext="The American rhinoceros, native to its prairies, is poached for its thick, blue denim hide. Sunscreen is necessary to survive here.",
        psy0mac="00:00:00:00:00:00",
        serial="00000000",
        age_pubkey="age1j7c4lzf86l3493mg8g7jhx5hawvnc4gxv0nlau7d9nmfgycalfesykwznl",
        age_key_path="/etc/progfiguration/age.key",
    ),
    roles=dict(
        seedboxk8s=dict(
            psyops_seedboxk8s_flux_deploy_id=AgeSecretReference("psyops_seedboxk8s_flux_deploy_id"),
            flux_agekey=AgeSecretReference("seedboxk8s_flux_age_key"),
            ca_key=AgeSecretReference("seedboxk8s_ca_key"),
            ca_crt=seedboxk8s_ca_crt,
        ),
    ),
)
