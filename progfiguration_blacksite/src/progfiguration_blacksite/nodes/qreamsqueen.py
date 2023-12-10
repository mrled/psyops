from progfiguration.inventory.nodes import InventoryNode

node = InventoryNode(
    address="qreamsqueen.example.com",
    user="root",
    ssh_host_fingerprint="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINQc2ZFWwIJTQMqizDtjbFI4sOvomqKnTMZ8pFsViGQK mrled@Naragua",
    sitedata=dict(
        notes="This is a test host that I use in qemu etc.",
        flavortext="TO BE FILLED IN BY OEM",
        psy0mac="ac:ed:de:ad:ba:be",
        serial="80085",
        age_pubkey="age1uzvulwlmdxfa2dcqjchpn4tev4aqtp42067ey2tgpen6mpm2g3xsvpkx2h",
    ),
    roles=dict(),
)
