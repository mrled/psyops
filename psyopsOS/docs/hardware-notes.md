# Hardware notes

## Dell Optiplex 7050

* BIOS settings
    * SATA
        * Disable RAID, enable AHCI
        * Without this, Linux will not see the NVME drive
