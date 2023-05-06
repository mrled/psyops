"""Constants and global variables for the site package."""

from progfiguration.progfigtypes import Bunch


psyops_ssh_pubkey = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ/zN5QLrTpjL1Qb8oaSniRQSwWpe5ovenQZOLyeHn7m conspirator@PSYOPS"
)

home_domain = Bunch(
    dns="home.micahrl.com",
    zone="Z32HSYI0AGMFV9",
)
