from progfiguration.inventory.nodes import InventoryNode


node = InventoryNode(
    address="kenasus.home.micahrl.com",
    user="root",
    ssh_host_fingerprint="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ/QG0TrDipsZb+CFMMp+7VpFkKkUikf2eqECWi4TKRp",
    sitedata=dict(
        flavortext="A great sea of windmills tears apart the atmosphere. Astronauts are trained here, as most breathable air is lost to these machines.",
        # Onboard NIC is broken?
        # psy0mac="00:e0:4c:00:00:52", # Some shitty USB NIC
        psy0mac="c4:62:37:06:66:5a",  # 2.5Gbe M.2
        serial="1023GQ2",
        age_pubkey="age1z85wazw58mj6e20jfdx9t054m5ymzs84es48n6ntk7nste5vl9cqmtu5wh",
    ),
    roles=dict(
        k3s={
            "start_k3s": True,
        },
    ),
)
