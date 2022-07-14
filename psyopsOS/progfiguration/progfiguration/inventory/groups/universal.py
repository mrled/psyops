"""The universal group - all nodes are in this group"""

from progfiguration.inventory.invhelpers import Bunch


group = Bunch(
    testattribute="test value",
    roles=Bunch(
        alpine_postboot_config={
            "timezone": "US/Central",
        },
        datadisk={
            "wipefs_if_no_vg": True,
        },
    ),
)
