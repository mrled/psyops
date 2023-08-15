from progfiguration.inventory.nodes import InventoryNode


node = InventoryNode(
    address="172.16.49.129",
    user="root",
    notes="This node is used for testing in various VMs, and the key might be re-used.",
    flavortext="",
    age_pubkey="age1djzr8h7ycsrnu5r55m7sd72esk04zm5nsuterlmx6vvcxyhcnd8qfhdapc",
    ssh_host_fingerprint="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILbFK8hAMDda5556Nn2Nq/SLK6opdZRrJhGI8sJqJYC1",
    psy0mac="00:0c:29:02:dd:01",
    serial="",
    roles=dict(
        datadisk={
            "ramoffload": True,
        },
        k3s={
            "start_k3s": False,
        },
    ),
)
