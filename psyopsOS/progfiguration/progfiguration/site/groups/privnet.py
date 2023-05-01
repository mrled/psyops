from pathlib import Path

from progfiguration.age import AgeSecretReference
from progfiguration.inventory.roles import RoleResultReference
from progfiguration.localhost.disks import (
    FilesystemSpec,
    LvmLvSpec,
    PartitionSpec,
    WholeDiskSpec,
)
from progfiguration.progfigtypes import Bunch


group = Bunch(
    roles=Bunch(
        blockdevparty={
            "wholedisks": [
                # Currently unused
                WholeDiskSpec("/dev/nvme0n1", None, None, False),
            ],
            "partitions": [
                PartitionSpec("/dev/sda", "psyopsosdata", "0%", "100%", volgroup="psyopsos_datadiskvg", encrypt=True),
            ],
            "volumes": [
                LvmLvSpec("datadisklv", "psyopsos_datadiskvg", r"100%FREE", FilesystemSpec("ext4", "psyopsos_data")),
            ],
        },
        acmeupdater_base={
            "role_dir": Path("/psyopsos-data/roles/acmeupdater"),
            "sshkey": AgeSecretReference("acmeupdater_sshkey"),
            # "acme_email": "psyops@micahrl.com",
        },
        acmeupdater_synology={
            "legodir": RoleResultReference("acmeupdater_base", "legodir"),
            "aws_region": "us-east-2",
            "aws_access_key_id": AgeSecretReference("acmeupdater_aws_access_key_id"),
            "aws_secret_access_key": AgeSecretReference("acmeupdater_aws_secret_access_key"),
            "aws_zone": "Z32HSYI0AGMFV9",
            "acmedns_email": "psyops@micahrl.com",
            "domain": "chenoska.home.micahrl.com",
            "synology_user": "admin",
            "synology_host": "chenoska.home.micahrl.com",
            "acmeupdater_user": "acmeupdater",
            "capthook_hooksdir": RoleResultReference("capthook", "hooksdir"),
            "capthook_user": RoleResultReference("capthook", "username"),
            "synology_ssh_keyscan": "chenoska.home.micahrl.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJLuNmro3TGPnbqZfiAxWf5oVeCFHp/waQVZ/yod5rU8",
            "job_suffix": "chenoska",
        },
        pullbackup={
            "sshkey": AgeSecretReference("pullbackup_sshkey"),
        },
        pullbackup_email={
            "me_micahrl_com_password": AgeSecretReference("mrled_fastmail_password"),
            "role_dir": Path("/psyopsos-data/roles/pullbackup_email"),
            "capthook_hooksdir": RoleResultReference("capthook", "hooksdir"),
            "capthook_user": RoleResultReference("capthook", "username"),
            "job_suffix": "mrled_fastmail",
            "pullbackup_user": RoleResultReference("pullbackup", "username"),
        },
        pullbackup_unifi={
            "role_dir": Path("/psyopsos-data/roles/pullbackup_unifi"),
            "capthook_hooksdir": RoleResultReference("capthook", "hooksdir"),
            "capthook_user": RoleResultReference("capthook", "username"),
            "job_suffix": "cloudkey",
            "pullbackup_user": RoleResultReference("pullbackup", "username"),
            "cloudkey_hostname": "unifi.home.micahrl.com",
            "cloudkey_pubkey": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM2LuwS1ESwK8pK+hG8nx0nXGgClD3WrZzls2oxH8W6H",
            "cloudkey_user": "mrladmin",
        },
        syslog_collector={
            "logdir": Path("/psyopsos-data/roles/syslog_collector/syslog"),
        },
    ),
)
