"""My home k3s cluster"""

from progfiguration.age import AgeSecretReference
from progfiguration.inventory.invhelpers import Bunch

group = Bunch(
    roles=Bunch(
        datadisk={
            "lvsize": r"256G",
        },
        k3s={
            "kube_vip_address": "192.168.1.200",
        },
    ),
)
