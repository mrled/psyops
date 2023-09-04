"""Constants and global variables for the site package."""


class Bunch:
    """A nice little object wrapper.

    From <https://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/?in=user-97991>
    """

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


psyops_ssh_pubkey = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ/zN5QLrTpjL1Qb8oaSniRQSwWpe5ovenQZOLyeHn7m conspirator@PSYOPS"
)

home_domain = Bunch(
    dns="home.micahrl.com",
    zone="Z32HSYI0AGMFV9",
)
