"""A very dumb user database.

Users need to be created on every boot because rootfs is ephemeral.
If we leave UID assignment up to the operating system,
then we can't guarantee that the same user will have the same UID across reboots.

This is a problem if the user will own files on non-ephemeral storage.

Site UID and GID ranges
-----------------------

We use 65536-256000 for managed UID/GID.

About UID and GID ranges
------------------------

* Special Linux UIDs:

    * 0: root
    * 65534: nobody
    * 65535: "16-bit (uid_t) -1", not usable
    * 4294967294: "32-bit (uid_t) -2", not usable

* Special Linux GIDs:

    * 0: root
    * 5: tty

* Alpine Linux UID/GID ranges:

    * Alpine appears to use 0-999 for system UID/GID and 1000+ for user UID/GID
    * BusyBox `adduser` fails to add a user with a UID above 256000 as of 2023.

* Documentation worth reading

    * `Users, Groups, UIDs and GIDs on systemd Systems <https://systemd.io/UIDS-GIDS/>`_
    * `Can't add a user with a high UID in docker Alpine <https://stackoverflow.com/questions/41807026/>`_

"""


users = {
    "mrled": 65536,
    "nebula": 65537,
    "pullbackup": 65538,
    "acmeupdater": 65539,
    "capthook": 65540,
    "archivebox": 65541,
    "synergist": 65542,
}
"""List of usernames and UIDs.

Keep this list in order of increasing UID.
"""

groups = {
    "mrled": 65536,
    "nebula": 65537,
    "pullbackup": 65538,
    "acmeupdater": 65539,
    "capthook": 65540,
    "archivebox": 65541,
    "synergist": 65542,
}
"""List of groupnames and GIDs.

Keep this list in order of increasing GID.
"""


def check_duplicate_uid_gid():
    """Check for duplicate UIDs and GIDs

    This function is called in module initialization.
    """
    uids = set()
    gids = set()
    for username, uid in users.items():
        if uid in uids:
            raise ValueError(f"Duplicate UID {uid} for user {username}")
        uids.add(uid)
    for groupname, gid in groups.items():
        if gid in gids:
            raise ValueError(f"Duplicate GID {gid} for group {groupname}")
        gids.add(gid)


# We call this function in module initialization intentionally.
# UIDs and GIDs should never be duplicated,
# so we want to catch any errors as early as possible.
check_duplicate_uid_gid()
