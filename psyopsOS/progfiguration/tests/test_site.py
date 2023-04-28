"""Site-specific tests"""

import pdb
import unittest

from progfiguration import site
from progfiguration.inventory import Inventory

from tests import PdbTestCase, pdbexc


class TestRun(PdbTestCase):
    @classmethod
    @pdbexc
    def setUpClass(cls):
        cls.inventory = Inventory(site.package_inventory_file, None)
        if not cls.inventory.controller.age:
            raise Exception(
                "Controller age is not set - are you running this from the controller with a decrypted secrets volume?"
            )

    @pdbexc
    def test_inventory_all_roles(self):
        """Test that all roles can be instantiated

        Instantiation requires decrypting secrets (which requires the controller age),
        and properly dereferencing secrets and role results.
        """

        for nodename in self.inventory.nodes:
            for role in self.inventory.node_role_list(nodename):
                with self.subTest(msg=f"nodename={nodename}, role={role}"):
                    pass


if __name__ == "__main__":
    unittest.main()
