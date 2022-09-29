"""synergycontroller role

The synergy controller for my keyboard and mouse multiplexing setup.
"""

import os
import re
import shutil
import subprocess
import textwrap
import time
from importlib.resources import files as importlib_resources_files

from progfiguration.localhost import LocalhostLinuxPsyopsOs
from progfiguration.roles.datadisk import is_mountpoint

import requests


module_files = importlib_resources_files("progfiguration.roles.synergycontroller")


defaults = {
    "user": "synergist",
    "user_gecos": "Synergist",
}


def apply(
    localhost: LocalhostLinuxPsyopsOs,
    user: str,
    user_gecos: str,
    synergy_priv_key: str,
    synergy_pub_key: str,
    synergy_fingerprints_local: str,
    synergy_serial_key: str,
    synergy_server_screenname: str,
):

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

    try:
        subprocess.run(["id", user], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        subprocess.run(["adduser", "-g", user_gecos, "-D", user])
        subprocess.run(["adduser", user, "flatpak"])
        subprocess.run(["adduser", user, "input"])
        subprocess.run(["adduser", user, "video"])

    # Tell lightdm to use 1920x1080
    # Via <https://askubuntu.com/questions/73804/wrong-login-screen-resolution>
    # The output name of HDMI-1 you can get from running `xrandr -q` in an xterm.
    # This is useful for us bc it's reasonable for the monitor and works at 60hz.
    # By default, it was doing 3840x1260 (? I think) and only 30hz,
    # which I think is a limitation of the HDMI version on the hardware but I'm not sure.
    displaysetup_path = "/var/psyopsOS/lightdm-display-setup.sh"
    displaysetup_contents = textwrap.dedent(
        """\
        #!/bin/sh
        xrandr --output HDMI-1 --primary --mode 1920x1080
        """
    )
    localhost.set_file_contents(displaysetup_path, displaysetup_contents, "root", "root", 0o0755)

    # Modify PAM configuration
    # - Get rid of elogind from PAM
    #   By default all of this is optional anyway,
    #   but it results in log noise.
    # - Disable GNOME keyring from lightdm-autologin
    #   <https://github.com/canonical/lightdm/issues/178>
    #   Also disable kwallet while we're at it I guess, idk
    for pamd_file in os.listdir("/etc/pam.d"):
        pamd_path = os.path.join("/etc/pam.d", pamd_file)
        print(pamd_path)
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
    xpx = f"/home/{user}/.config/xfce4/xfconf/xfce-perchannel-xml"
    localhost.makedirs(xpx, owner=user, mode=0o0700)
    for xfile in ["xfce4-screensaver.xml", "xfce4-power-manager.xml"]:
        shutil.copy(module_files.joinpath(f"xfce_perchannel_xml/{xfile}"), f"{xpx}/{xfile}")
        shutil.chown(f"{xpx}/{xfile}", user)

    synergyhome = os.path.expanduser(f"~{user}")
    if not synergyhome or not os.path.exists(synergyhome):
        raise Exception(f"Synergy user {user} does not have a homedir?")

    autostart_dir = os.path.join(synergyhome, ".config", "autostart")
    localhost.cp(
        module_files.joinpath("autostart/Terminal.desktop"),
        f"{autostart_dir}/Terminal.desktop",
        owner=user,
        mode=0o0600,
        dirmode=0o0700,
    )
    localhost.template(
        module_files.joinpath("autostart/Synergy.desktop.template"),
        f"{autostart_dir}/Synergy.desktop",
        {"user": user},
        owner=user,
        mode=0o0600,
        dirmode=0o0700,
    )

    # Configure Synergy itself
    dotsynergy = os.path.join(synergyhome, ".synergy")
    localhost.set_file_contents(
        os.path.join(dotsynergy, "SSL", "Synergy.pem"),
        "\n".join([synergy_priv_key, synergy_pub_key]),
        owner=user,
        mode=0o0600,
        dirmode=0o0700,
    )
    localhost.set_file_contents(
        os.path.join(dotsynergy, "SSL", "Fingerprints", "Local.txt"),
        synergy_fingerprints_local,
        owner=user,
        mode=0o0600,
        dirmode=0o0700,
    )
    localhost.cp(
        module_files.joinpath("synergy.conf"), os.path.join(synergyhome, "synergy.conf"), owner=user, mode=0o0644
    )
    localhost.template(
        module_files.joinpath("internal.Synergy.conf.template"),
        f"{synergyhome}/.var/app/com.symless.Synergy/config/Synergy/Synergy.conf",
        {"user": user, "serial": synergy_serial_key, "screenname": synergy_server_screenname},
        owner=user,
        mode=0o0600,
    )

    # Configure lightdm
    localhost.template(
        module_files.joinpath("lightdm.conf.template"),
        "/etc/lightdm/lightdm.conf",
        {"user": user},
        owner="root",
        group="root",
        mode=0o0644,
    )

    flatpak_overlay = "/psyopsos-data/overlays/var-lib-flatpak"
    if not is_mountpoint("/var/lib/flatpak"):
        localhost.makedirs(flatpak_overlay, owner="root", group="root", mode=0o0755)
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

    if subprocess.run("flatpak info com.symless.Synergy", shell=True, check=False, capture_output=True).returncode != 0:
        # Synergy isn't installed yet...

        # subprocess.run(["curl", "-o", "/tmp/synergy.flatpak", synergy_flatpak_uri])
        # subprocess.run("flatpak install -y /tmp/synergy.flatpak", shell=True, check=True)
        synergy_flatpak = "/psyopsos-data/roles/synergycontroller/synergy_1.14.5-stable.0cafa5d7.flatpak"
        if not os.path.exists(synergy_flatpak):
            # TODO: Download this from Symless automatically
            # I'm not sure how their auth works so right now you have to copy it to this location manually
            # TODO: Maybe just host the Symless flatpak somewhere and sign it with my own key?
            raise Exception(f"Synergy flatpak not downloaded to {synergy_flatpak}, aborting...")

        subprocess.run(f"flatpak install -y {synergy_flatpak}", shell=True, check=True)

    # Configure and start lightdm
    localhost.template(
        module_files.joinpath("lightdm.conf.template"),
        "/etc/lightdm/lightdm.conf",
        {"user": user},
        owner=user,
        mode=0o0644,
    )
    subprocess.run(["rc-service", "dbus", "start"], check=True)
    subprocess.run(["rc-service", "udev", "start"], check=True)
    subprocess.run(["rc-service", "lightdm", "start"], check=True)
    time.sleep(2)
    # The first start it doesn't seem to autologin correctly?
    # So here's a fucked up hack.
    subprocess.run(["rc-service", "lightdm", "restart"], check=True)
