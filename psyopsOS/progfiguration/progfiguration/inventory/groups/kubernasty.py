"""My home k3s cluster"""

from progfiguration.age import AgeSecretReference
from progfiguration.inventory.invhelpers import Bunch

group = Bunch(
    roles=Bunch(
        k3s={
            "kube_vip_address": "192.168.1.200",
        },
    ),
)
