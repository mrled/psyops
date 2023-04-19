from progfiguration.inventory.nodes import InventoryNode
from progfiguration.progfigtypes import Bunch

node = InventoryNode(
    address="jesseta.home.micahrl.com",
    user="root",
    notes="",
    flavortext="A war is being fought here between taxidermied animals and abandoned theme park animatronics, yet all we can perceive is stillness.",
    age_pubkey="age19ylpmjad3kl8lvhzt8djpeuq4y2cdw6wfy6zklf4zrdm7yuv9vfs49qmvg",
    ssh_host_fingerprint="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFf2+Cb4VBkzkbIBqP9DDAAjaJmj1AKixce1n89Kx++R",
    psy0mac="d8:9e:f3:90:cd:98",
    serial="J4S0WP2",
    roles=Bunch(
        k3s={
            "start_k3s": True,
        },
    ),
)
