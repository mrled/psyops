"""synergycontroller role

The synergy controller for my keyboard and mouse multiplexing setup.
"""

from dataclasses import dataclass, field
import os
import re
import shutil
import subprocess
import textwrap
import time
from typing import List
from progfiguration import ssh

from progfiguration.cmd import run
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.localhost import LocalhostLinux, authorized_keys
from progfiguration.localhost.disks import is_mountpoint

import requests


def install_vscode_remote_prereqs():
    """Install these for vscode server

    The user may need to have bash set as their shell
    """
    packages = [
        "bash",
        "gcompat",
        "libstdc++6",
        "libuser",
        "wget",
    ]
    subprocess.run(["apk", "add"] + packages, check=True)

    # We have to allow TCP forwarding for VS Code remoting to work
    with open("/etc/ssh/sshd_config") as fp:
        sshd_config = fp.readlines()
    new_sshd_config = []

    did_set_tcp_forwarding = False
    for line in sshd_config:
        if line.startswith("AllowTcpForwarding "):
            new_sshd_config += ["AllowTcpForwarding yes"]
            did_set_tcp_forwarding = True
        else:
            new_sshd_config += [line]
    if not did_set_tcp_forwarding:
        new_sshd_config == ["AllowTcpForwarding yes"]

    with open("/etc/ssh/sshd_config", "w") as fp:
        fp.writelines(new_sshd_config)


def install_teensy_loader_cli(
    localhost: LocalhostLinux,
    clone_user: str,
    clone_parent: str,
    repo_uri="https://github.com/PaulStoffregen/teensy_loader_cli",
    repo_name="teensy_loader_cli",
):
    """Install teensy_loader_cli, which is required to flash QMK firmware

    `qmk flash` tries to use this behind the scenes to flash my ErgoDox.
    You can also run it directly to flash.
    """
    packages = [
        "libusb",
        "libusb-compat",
        "libusb-compat-dev",
        "libusb-dev",
        "make",
        "musl-dev",
    ]
    subprocess.run(["apk", "add"] + packages, check=True)
    clone_path = os.path.join(clone_parent, repo_name)
    if os.path.exists(clone_path):
        subprocess.run(["git", "pull"], user=clone_user, cwd=clone_path)
    else:
        subprocess.run(["git", "clone", repo_uri], user=clone_user, cwd=clone_parent)
    subprocess.run(["make"], user=clone_user, cwd=clone_path)
    shutil.copy(f"{clone_path}/teensy_loader_cli", "/usr/local/bin")


def install_synergy():

    # Some of these are required or else X does not accept input at all
    # <https://gitlab.alpinelinux.org/alpine/aports/-/issues/5422>
    packages = [
        "adwaita-icon-theme",
        "dbus",
        "flatpak",
        "libev-dev",
        "lightdm-gtk-greeter",
        "plymouth",
        "pm-utils",
        "tmux",
        "xf86-input-evdev",
        "xf86-input-libinput",
        "xfce4",
        "xfce4-screensaver",
        "xfce4-session",
        "xfce4-terminal",
        "xorg-server",
        "xorg-server-common",
        "xorg-server-dev",
        "xorgproto",
        "xorgxrdp",
        "xorgxrdp-dev",
        "xrandr",
        "xterm",
        "udev",
    ]
    subprocess.run(["apk", "add"] + packages, check=True)


def install_qmk_prereqs():
    packages = [
        # Required for QMK, including compiling and flashing firmware
        "avr-libc",
        "avrdude",
        "gcc-arm-none-eabi",
        "gcc-avr",
        "dfu-util@edgetesting",
        "dfu-programmer@edgetesting",
        "make",
    ]

    subprocess.run(["apk", "add"] + packages, check=True)


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    user: str = "synergist"
    user_authorized_keys: List[str] = field(
        default_factory=lambda: [
            r"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ/zN5QLrTpjL1Qb8oaSniRQSwWpe5ovenQZOLyeHn7m conspirator@PSYOPS",
            r"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMN/4Rdkz4vlGaQRvhmhLhkaH0CfhNnoggGBBknz17+u mrled@haluth.local",
        ]
    )
    user_gecos: str = "Synergist"
    synergy_priv_key: str
    synergy_pub_key: str
    synergy_fingerprints_local: str
    synergy_serial_key: str
    synergy_server_screenname: str

    # A deploy keyh created for my qmk_firmware fork
    github_deploy_key: str

    def apply(self):

        groupname = self.user

        install_synergy()

        run("apk add bluez")
        run("rc-servie bluetooth start")
        run("rc-update add bluetooth")
        # Pairing:
        # <https://wiki.archlinux.org/title/Bluetooth#Pairing>
        # bluetoothctl
        # scan on
        # pair <MAC>
        # trust <MAC>
        # connect <MAC>

        try:
            subprocess.run(["id", self.user], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Bash is required to be the user's shell for vscode remote
            subprocess.run(["apk", "add", "bash"])
            # Create the user
            subprocess.run(["adduser", "-g", self.user_gecos, "-D", "-s", "/bin/bash", self.user])
            # Unlock the account without setting a password (only SSH keys can be used to connect)
            subprocess.run(["usermod", "-p", "*", self.user])
            # Add the user to required groups
            subprocess.run(["adduser", self.user, "flatpak"])
            subprocess.run(["adduser", self.user, "input"])
            subprocess.run(["adduser", self.user, "video"])
        authorized_keys.add_idempotently(self.localhost, self.user, self.user_authorized_keys)
        self.localhost.set_file_contents(
            "/etc/sudoers.d/synergist-teensy",
            "synergist ALL = NOPASSWD: /usr/local/bin/teensy_loader_cli",
            "root",
            "root",
            0o600,
        )

        deploykey_path = "/home/synergist/.ssh/id_qmk_firmware"

        self.localhost.set_file_contents(deploykey_path, self.github_deploy_key, self.user, self.user, 0o0600, 0o0700)
        # TODO: Now use this pubkey with qmk

        # Tell lightdm to use 1920x1080
        # Via <https://askubuntu.com/questions/73804/wrong-login-screen-resolution>
        # The output name of HDMI-1 you can get from running `xrandr -q` in an xterm.
        # This is useful for us bc it's reasonable for the monitor and works at 60hz.
        # By default, it was doing 3840x1260 (? I think) and only 30hz,
        # which I think is a limitation of the HDMI version on the hardware but I'm not sure.
        displaysetup_path = "/var/psyopsOS/lightdm-display-setup.sh"
        displaysetup_contents = textwrap.dedent(
            f"""\
            #!/bin/sh
            # Allow the user to connect to the X server, which synergys must do
            xhost +si:localuser:{self.user}
            """
        )
        self.localhost.set_file_contents(displaysetup_path, displaysetup_contents, "root", "root", 0o0755)
        subprocess.run(["apk", "add", "xhost"], check=True)

        # Modify PAM configuration
        # - Get rid of elogind from PAM
        #   By default all of this is optional anyway,
        #   but it results in log noise.
        # - Disable GNOME keyring from lightdm-autologin
        #   <https://github.com/canonical/lightdm/issues/178>
        #   Also disable kwallet while we're at it I guess, idk
        for pamd_file in os.listdir("/etc/pam.d"):
            pamd_path = os.path.join("/etc/pam.d", pamd_file)
            # print(pamd_path)
            if not os.path.isfile(pamd_path):
                continue
            if os.stat(pamd_path).st_size == 0:
                continue
            with open(pamd_path) as fd:
                contents = fd.readlines()
            newcontents = []
            for line in contents:
                if line.startswith("#"):
                    newcontents.append(line)
                elif re.search(".*elogind.*", line):
                    newcontents.append(f"#{line}")
                elif pamd_file == "lightdm-autologin" and (
                    re.search(".*gnome_keyring.*", line) or re.search(".*kwallet.*", line)
                ):
                    newcontents.append(f"#{line}")
                else:
                    newcontents.append(line)
            with open(pamd_path, "w") as fd:
                fd.writelines(newcontents)

        # Don't let the screensaver lock the screen
        # This user has no password, so it cannot unlock the screen without restarting lightdm
        xpx = f"/home/{self.user}/.config/xfce4/xfconf/xfce-perchannel-xml"
        self.localhost.makedirs(xpx, owner=self.user, mode=0o0700)
        for xfile in ["xfce4-screensaver.xml", "xfce4-power-manager.xml"]:
            self.localhost.cp(self.role_file(f"xfce_perchannel_xml/{xfile}"), f"{xpx}/{xfile}", owner=self.user)

        synergyhome = os.path.expanduser(f"~{self.user}")
        if not synergyhome or not os.path.exists(synergyhome):
            raise Exception(f"Synergy user {self.user} does not have a homedir?")

        # Install services etc
        self.localhost.cp(
            self.role_file("synergys.openrc.init"),
            f"/etc/init.d/synergys",
            owner="root",
            mode=0o0755,
        )
        self.localhost.temple(
            self.role_file("synergys.openrc.conf.temple"),
            f"/etc/conf.d/synergys",
            {
                "user": self.user,
                "group": groupname,
                "homedir": synergyhome,
            },
            owner=self.user,
            mode=0o0600,
            dirmode=0o0700,
        )
        self.localhost.temple(
            self.role_file("synergys-wrapper.sh.temple"),
            "/usr/lcoal/bin/synergys-wrapper.sh",
            {"user": self.user},
            owner="root",
            mode=0o0755,
        )

        # Configure Synergy itself
        dotsynergy = os.path.join(synergyhome, ".synergy")
        self.localhost.set_file_contents(
            os.path.join(dotsynergy, "SSL", "Synergy.pem"),
            "\n".join([self.synergy_priv_key, self.synergy_pub_key]),
            owner=self.user,
            mode=0o0600,
            dirmode=0o0700,
        )
        self.localhost.set_file_contents(
            os.path.join(dotsynergy, "SSL", "Fingerprints", "Local.txt"),
            self.synergy_fingerprints_local,
            owner=self.user,
            mode=0o0600,
            dirmode=0o0700,
        )
        self.localhost.cp(
            self.role_file("synergy.conf"), os.path.join(synergyhome, "synergy.conf"), owner=self.user, mode=0o0644
        )
        self.localhost.template(
            self.role_file("internal.Synergy.conf.template"),
            f"{synergyhome}/.var/app/com.symless.Synergy/config/Synergy/Synergy.conf",
            {"user": self.user, "serial": self.synergy_serial_key, "screenname": self.synergy_server_screenname},
            owner=self.user,
            mode=0o0600,
        )

        flatpak_overlay = "/psyopsos-data/overlays/var-lib-flatpak"
        if not is_mountpoint("/var/lib/flatpak"):
            self.localhost.makedirs(flatpak_overlay, owner="root", group="root", mode=0o0755)
            subprocess.run(["mount", "-o", "bind", flatpak_overlay, "/var/lib/flatpak"])

        if not os.path.exists("/var/lib/flatpak/repo/flathub.trustedkeys.gpg"):
            flathub_gpg = requests.get("https://flathub.org/repo/flathub.gpg", allow_redirects=True)
            with open("/tmp/flathub.gpg", "wb") as fd:
                fd.write(flathub_gpg.content)
            subprocess.run(
                "flatpak remote-add --gpg-import /tmp/flathub.gpg flathub https://flathub.org/repo/flathub.flatpakrepo",
                shell=True,
                check=True,
            )

        if (
            subprocess.run("flatpak info com.symless.Synergy", shell=True, check=False, capture_output=True).returncode
            != 0
        ):
            # Synergy isn't installed yet...

            # subprocess.run(["curl", "-o", "/tmp/synergy.flatpak", synergy_flatpak_uri])
            # subprocess.run("flatpak install -y /tmp/synergy.flatpak", shell=True, check=True)
            synergy_flatpak = "/psyopsos-data/roles/synergycontroller/synergy_1.14.6-snapshot.88fdd263.flatpak"
            if not os.path.exists(synergy_flatpak):
                # TODO: Download this from Symless automatically
                # I'm not sure how their auth works so right now you have to copy it to this location manually
                # TODO: Maybe just host the Symless flatpak somewhere and sign it with my own key?
                raise Exception(f"Synergy flatpak not downloaded to {synergy_flatpak}, aborting...")

            subprocess.run(f"flatpak install -y {synergy_flatpak}", shell=True, check=True)

        # Configure and start lightdm
        self.localhost.template(
            self.role_file("lightdm.conf.template"),
            "/etc/lightdm/lightdm.conf",
            {"user": self.user},
            owner=self.user,
            mode=0o0644,
        )
        subprocess.run(["rc-service", "dbus", "start"], check=True)
        subprocess.run(["rc-service", "udev", "start"], check=True)
        subprocess.run(["rc-service", "mdev", "start"], check=True)
        subprocess.run(["setup-xorg-base"], check=True)
        subprocess.run(["rc-service", "lightdm", "start"], check=True)
        time.sleep(2)
        # # The first start it doesn't seem to autologin correctly?
        # # So here's a fucked up hack.
        # subprocess.run(["rc-service", "lightdm", "restart"], check=True)
        subprocess.run(["rc-service", "synergys", "start"], check=True)

        # TODO: !!! autologin STILL isn't working correctly !!! FIXME !!!

        synergist_data = "/psyopsos-data/roles/synergycontroller/synergist"
        self.localhost.makedirs(synergist_data, self.user, mode=0o0755)

        install_qmk_prereqs()
        install_teensy_loader_cli(self.localhost, self.user, synergist_data)

        qmk_home = "/psyopsos-data/roles/synergycontroller/qmk_firmware"
        run(f"sudo -u {self.user} python3 -m pip install --user qmk")

        install_vscode_remote_prereqs()

        # Can now configure QMK:
        # qmk setup -H /psyopsos-data/roles/synergycontroller/synergist/qmk_firmware mrled/qmk_firmware
        #
        # git config --local core.sshCommand "/usr/bin/ssh -i $HOME/.ssh/id_qmk_firmware"
        # git remote set-url origin git@github.com:mrled/qmk_firmware.git
        #
        # sudo cp /psyopsos-data/roles/synergycontroller/synergist/qmk_firmware/util/udev/50-qmk.rules /etc/udev/rules.d/
        # ... not sure if that will actually work
        #
        # And build firmware:
        # qmk compile -kb ergodox_ez/shine -km mrled
        #
        # In theory you can flash with
        # qmk flash -kb ergodox_ez/shine -km mrled
        #
        # However, because something something udev something Alpine something something,
        # it's easier to just do
        # sudo teensy_loader_cli -w -v -mmcu=atmega32u4 /psyopsos-data/roles/synergycontroller/synergist/qmk_firmware/.build/ergodox_ez_shine_mrled.hex
        #
        # Ploopy trackball: rev 1.004
