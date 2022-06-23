from progfiguration.inventory.invhelpers import Bunch

node = Bunch(
    notes="",
    motd=Bunch(
        flavor="A great sea of windmills tears apart the atmosphere. Astronauts are trained here, as most breathable air is lost to these machines.",
    ),
    pubkey="age1z85wazw58mj6e20jfdx9t054m5ymzs84es48n6ntk7nste5vl9cqmtu5wh",
    roles=Bunch(
        k3s={
            "start_k3s": True,
        },
    ),
    serial="1023GQ2",
)
