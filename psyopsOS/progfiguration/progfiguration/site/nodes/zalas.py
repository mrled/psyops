from progfiguration.inventory.nodes import InventoryNode
from progfiguration.progfigtypes import Bunch


node = InventoryNode(
    address="zalas.home.micahrl.com",
    user="root",
    notes="",
    flavortext="An endless shopping mall with an equally endless arcade of black neon, whose only available game is a rehearsal of thermonuclear war.",
    age_pubkey="age1y2q4ftlq087sxetvm2uv8rqftn9x2maqsrhuyyf6zzjvfhr37afq56kwpk",
    ssh_host_fingerprint="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEo7G+BdBF/o/cnTSQxOxdgSXY6ug01XKBp1xgaQbDBq",
    psy0mac="d8:9e:f3:9a:3f:2a",
    serial="10K7GQ2",
    roles=Bunch(
        k3s={
            "start_k3s": True,
        },
    ),
)
