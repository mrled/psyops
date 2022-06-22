"""The universal group - all nodes are in this group"""

from progfiguration.inventory.invhelpers import Bunch


group = Bunch(
    testattribute="test value",
    roles=Bunch(
        datadisk={},
    ),
)
