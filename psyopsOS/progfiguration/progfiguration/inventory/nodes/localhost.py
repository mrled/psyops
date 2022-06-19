"""A localhost node

Useful for testing code changes
"""

from progfiguration.inventory.invhelpers import Bunch


node = Bunch(
    notes = 'The localhost node',
    motd = Bunch(
        flavor = "",
    ),
    pubkey = '',
    # groups = [
    #     'localhost',
    # ],
    roles = Bunch(
        localhosttest = Bunch(
            test_val_from_node_role_name = "A test vale from the node configuration for this specific role name, asdf",
        )
    ),
    serial = "",
)
