from progfiguration.inventory.invhelpers import Bunch


node = Bunch(
    notes="This node is used for testing in various VMs, and the key might be re-used.",
    motd=Bunch(
        flavor="",
    ),
    pubkey="age1djzr8h7ycsrnu5r55m7sd72esk04zm5nsuterlmx6vvcxyhcnd8qfhdapc",
    roles=Bunch(
        k3s={
            "start_k3s": False,
        },
    ),
    nics={
        'psy0': '00:0c:29:02:dd:01',
    },
    serial="",
)
