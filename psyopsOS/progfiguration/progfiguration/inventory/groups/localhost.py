"""A test group for the localhost node"""

from progfiguration.inventory.invhelpers import Bunch


group = Bunch(
    roles = Bunch(
        localhostrole = Bunch(
            localhost_group_testval = "Test value from the localhost group, hi",
        ),
    ),
)
