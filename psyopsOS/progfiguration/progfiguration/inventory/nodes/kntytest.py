from progfiguration.inventory.invhelpers import Bunch


# from progfiguration.inventory.nodes import Bunch, NodeConfiguration


# node = {
#     "notes": 'This node is used for testing in various VMs, and the key might be re-used.',
#     'motd': {
#         'flavor': "",
#     },
#     'pubkey': 'age1djzr8h7ycsrnu5r55m7sd72esk04zm5nsuterlmx6vvcxyhcnd8qfhdapc',
#     'tags': [
#         "kubernasty",
#         "testhosts",
#     ],
#     'roles': [
#         'skunkworks',
#         'kubernasty',
#     ],
#     'serial': "",
# }


# notes = 'This node is used for testing in various VMs, and the key might be re-used.'
# motd = {
#     'flavor': "",
# }
# pubkey = 'age1djzr8h7ycsrnu5r55m7sd72esk04zm5nsuterlmx6vvcxyhcnd8qfhdapc'
# tags = [
#     "kubernasty",
#     "testhosts",
# ]
# roles = [
#     'skunkworks',
#     'kubernasty',
# ]
# serial = ""


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
    serial="",
)
