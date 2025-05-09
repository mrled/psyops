from progfiguration.inventory.nodes import InventoryNode

node = InventoryNode(
    address="agassiz.home.micahrl.com",
    user="root",
    ssh_host_fingerprint="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKEjC3ddVF7J0yJWSbGeEZv9bZ1CtGT70I6k0tRLf4pZ",
    sitedata=dict(
        flavortext="A colossal lead heart that connects all sewers throbs just beneath this state's surface. Its palpitations are felt as earthquakes.",
        # psy0mac="d8:9e:f3:86:65:ee", # onboard
        psy0mac="c4:62:37:06:65:1e",  # 2.5Gbe M.2
        serial="G6LMCP2",
        age_pubkey="age17wp408dyw8s4tszh230t92k4gyeeq3se48sx7yjkpmempja6xvgqnamqp3",
    ),
    roles=dict(
        k3s={
            "start_k3s": True,
        },
    ),
)
