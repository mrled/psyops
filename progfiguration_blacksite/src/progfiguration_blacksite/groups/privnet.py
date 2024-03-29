from pathlib import Path

from progfiguration.inventory.roles import RoleCalculationReference
from progfiguration.localhost.disks import FilesystemSpec, LvmLvSpec, PartitionSpec
from progfiguration.sitehelpers.agesecrets import AgeSecretReference

from progfiguration_blacksite.sitelib import siteglobals


group = dict(
    roles=dict(
        blockdevparty={
            # WARNING: this uses the older style of encrypting the partition,
            # rather than the newer style of encrypting the whole disk first.
            # The newer style is better because we can't wipe disks without it,
            # but switching is disruptive.
            "wholedisks": [],
            "partitions": [
                PartitionSpec(
                    "/dev/sda",
                    "psyopsosdata",
                    "0%",
                    "100%",
                    volgroup="psyopsos_datadiskvg",
                    encrypt=True,
                ),
                PartitionSpec(
                    "/dev/nvme0n1",
                    "archivebox",
                    "0%",
                    "100%",
                    volgroup="archiveboxvg",
                    encrypt=True,
                ),
            ],
            "volumes": [
                LvmLvSpec(
                    "datadisklv",
                    "psyopsos_datadiskvg",
                    r"100%FREE",
                    FilesystemSpec("ext4", "psyopsos_data"),
                ),
                LvmLvSpec(
                    "archiveboxlv",
                    "archiveboxvg",
                    r"100%FREE",
                    FilesystemSpec("ext4", "archivebox"),
                ),
            ],
        },
        datadisk_v2={
            "ramoffload": True,
            "ramoffload_size_gb": 64,
            "ramoffload_directories": ["/var/lib/docker"],
        },
        acmeupdater_base={
            "role_dir": Path("/psyopsos-data/roles/acmeupdater"),
            "sshkey": AgeSecretReference("acmeupdater_sshkey"),
        },
        acmeupdater_synology={
            "legodir": RoleCalculationReference("acmeupdater_base", "legodir"),
            "aws_region": siteglobals.home_domain.aws_region,
            "aws_access_key_id": AgeSecretReference("acmeupdater_aws_access_key_id"),
            "aws_secret_access_key": AgeSecretReference("acmeupdater_aws_secret_access_key"),
            "aws_zone": siteglobals.home_domain.zone,
            "acmedns_email": siteglobals.psyops_email,
            "domain": "chenoska.home.micahrl.com",
            "synology_user": "mrladmin",
            "synology_host": "chenoska.home.micahrl.com",
            "acmeupdater_user": RoleCalculationReference("acmeupdater_base", "username"),
            "acmeupdater_sshid_name": RoleCalculationReference("acmeupdater_base", "sshid_name"),
            "capthook_hooksdir": RoleCalculationReference("capthook", "hooksdir"),
            "capthook_user": RoleCalculationReference("capthook", "username"),
            "synology_ssh_keyscan": "chenoska.home.micahrl.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJLuNmro3TGPnbqZfiAxWf5oVeCFHp/waQVZ/yod5rU8",
            "job_suffix": "chenoska",
        },
        acmeupdater_pikvm={
            "legodir": RoleCalculationReference("acmeupdater_base", "legodir"),
            "aws_region": siteglobals.home_domain.aws_region,
            "aws_access_key_id": AgeSecretReference("acmeupdater_aws_access_key_id"),
            "aws_secret_access_key": AgeSecretReference("acmeupdater_aws_secret_access_key"),
            "aws_zone": siteglobals.home_domain.zone,
            "acmedns_email": siteglobals.psyops_email,
            "domain": "yalda.home.micahrl.com",
            "acmeupdater_user": RoleCalculationReference("acmeupdater_base", "username"),
            "acmeupdater_sshid_name": RoleCalculationReference("acmeupdater_base", "sshid_name"),
            "capthook_hooksdir": RoleCalculationReference("capthook", "hooksdir"),
            "capthook_user": RoleCalculationReference("capthook", "username"),
            "pikvm_ssh_keyscan": "yalda.home.micahrl.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILoAe1SM0s3YWPE38dEYxA/x3JnzQI7WW5YqpIRBaI1y",
        },
        pullbackup={
            "sshkey": AgeSecretReference("pullbackup_sshkey"),
        },
        pullbackup_email={
            "me_micahrl_com_password": AgeSecretReference("mrled_fastmail_password"),
            "role_dir": Path("/psyopsos-data/roles/pullbackup_email"),
            "capthook_hooksdir": RoleCalculationReference("capthook", "hooksdir"),
            "capthook_user": RoleCalculationReference("capthook", "username"),
            "job_suffix": "mrled_fastmail",
            "pullbackup_user": RoleCalculationReference("pullbackup", "username"),
        },
        pullbackup_unifi={
            "role_dir": Path("/psyopsos-data/roles/pullbackup_unifi"),
            "capthook_hooksdir": RoleCalculationReference("capthook", "hooksdir"),
            "capthook_user": RoleCalculationReference("capthook", "username"),
            "job_suffix": "cloudkey",
            "pullbackup_user": RoleCalculationReference("pullbackup", "username"),
            "cloudkey_hostname": "unifi.home.micahrl.com",
            "cloudkey_pubkey": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM2LuwS1ESwK8pK+hG8nx0nXGgClD3WrZzls2oxH8W6H",
            "cloudkey_user": "mrladmin",
        },
        syslog_collector={
            "logdir": Path("/psyopsos-data/roles/syslog_collector/syslog"),
        },
        homeswarm={
            "roledir": Path("/mnt/homeswarm"),
            "balancer_domain": "homeswarm-traefik.home.micahrl.com",
            "acme_email": siteglobals.psyops_email,
            "acme_aws_region": siteglobals.home_domain.aws_region,
            "acme_aws_zone": siteglobals.home_domain.zone,
            "acme_aws_access_key_id": AgeSecretReference("acmeupdater_aws_access_key_id"),
            "acme_aws_secret_access_key": AgeSecretReference("acmeupdater_aws_secret_access_key"),
            "whoami_domain": "homeswarm-whoami.home.micahrl.com",
            "archivebox_domain": "archivebox.home.micahrl.com",
            "zerossl_kid": AgeSecretReference("zerossl_kid"),
            "zerossl_hmac": AgeSecretReference("zerossl_hmac"),
            "homeswarm_blockdevice": "/dev/mapper/archiveboxvg-archiveboxlv",
            "pihole_webpassword": AgeSecretReference("homeswarm_pihole_webpassword"),
            "pihole_domain": "homeswarm-pihole.home.micahrl.com",
        },
    ),
)
