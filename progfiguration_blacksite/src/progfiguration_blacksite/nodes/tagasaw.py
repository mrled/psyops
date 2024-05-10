from progfiguration.inventory.nodes import InventoryNode
from progfiguration.sitehelpers.agesecrets import AgeSecretReference

psyops_seedboxk8s_flux_deploy_id_pub = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILt/A31ST7QW45mG7MBJSmHg3483YCIIVHbNuNPUgXEn"
)

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
        ),
    ),
)
