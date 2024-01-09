"""Constant values"""

filesystems = {
    "efisys": {
        "label": "PSYOPSOSEFI",
        "mountpoint": "/mnt/psyopsOS/efisys",
    },
    "a": {
        "label": "psyopsOS-A",
        "mountpoint": "/mnt/psyopsOS/a",
    },
    "b": {
        "label": "psyopsOS-B",
        "mountpoint": "/mnt/psyopsOS/b",
    },
}
filesystems[filesystems["a"]["label"]] = filesystems["a"]
filesystems[filesystems["b"]["label"]] = filesystems["b"]
filesystems[filesystems["efisys"]["label"]] = filesystems["efisys"]
