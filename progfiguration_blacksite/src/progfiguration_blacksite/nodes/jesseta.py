from progfiguration.inventory.nodes import InventoryNode

node = InventoryNode(
    address="jesseta.home.micahrl.com",
    user="root",
    ssh_host_fingerprint="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFf2+Cb4VBkzkbIBqP9DDAAjaJmj1AKixce1n89Kx++R",
    sitedata=dict(
        flavortext="A war is being fought here between taxidermied animals and abandoned theme park animatronics, yet all we can perceive is stillness.",
        # psy0mac="d8:9e:f3:90:cd:98",  # onboard
        psy0mac="c8:4d:44:24:a1:e9",  # 2.5Gbe USB (temp, until the M.2 comes in)
        # psy0mac="",  # 2.5Gbe M.2
        serial="J4S0WP2",
        age_pubkey="age19ylpmjad3kl8lvhzt8djpeuq4y2cdw6wfy6zklf4zrdm7yuv9vfs49qmvg",
    ),
    roles=dict(
        k3s={
            "start_k3s": True,
        },
    ),
)
