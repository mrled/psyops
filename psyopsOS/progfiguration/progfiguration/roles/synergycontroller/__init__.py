"""synergycontroller role

The synergy controller for my keyboard and mouse multiplexing setup.
"""

import datetime
import os
import re
import shutil
import string
import subprocess
import textwrap
from importlib.resources import files as importlib_resources_files
from typing import Any, Dict

from progfiguration.facts import PsyopsOsNode
from progfiguration.roles.datadisk import is_mountpoint

import requests


module_files = importlib_resources_files("progfiguration.roles.synergycontroller")


defaults = {
    'user': 'synergist',
}


def apply(node: PsyopsOsNode, user: str, synergy_priv_key: str, synergy_pub_key: str, synergy_fingerprints_local: str):

    packages = [
        "adwaita-icon-theme",
        "dbus",
        "flatpak",
        "libev-dev",
        "lightdm-gtk-greeter",
        "plymouth",
        "pm-utils",
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
        subprocess.run(["adduser", "-D", user])
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
    displaysetup_contents = textwrap.dedent("""\
        #!/bin/sh
        xrandr --output HDMI-1 --primary --mode 1920x1080
        """)
    node.set_file_contents(displaysetup_path, displaysetup_contents, "root", "root", 0o0755)

    # Get rid of elogind from PAM
    # By default all of this is optional anyway,
    # but it results in log noise.
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
            if not line.startswith("#") and re.search(".*elogind.*", line):
                newcontents.append(f"#{line}")
            else:
                newcontents.append(line)
        with open(pamd_path, 'w') as fd:
            fd.writelines(newcontents)

    lightdm_conf_template_path = module_files.joinpath("lightdm.conf.template")
    with open(lightdm_conf_template_path) as fp:
        lightdm_conf_template = string.Template(fp.read())
    lightdm_conf = lightdm_conf_template.substitute(user=user)
    node.set_file_contents("/etc/lightdm/lightdm.conf", lightdm_conf, "root", "root", 0o0644)
    subprocess.run(["rc-service", "dbus", "start"], check=True)
    subprocess.run(["rc-service", "udev", "start"], check=True)
    subprocess.run(["rc-service", "lightdm", "restart"], check=True)

    synergyhome = os.path.expanduser(f"~{user}")
    if not synergyhome or not os.path.exists(synergyhome):
        raise Exception(f"Synergy user {user} does not have a homedir?")

    autostart_dir = os.path.join(synergyhome, ".config", "autostart")
    # synergys_autostart = os.path.join(autostart_dir, "synergys.desktop")
    # node.makedirs(autostart_dir, owner=user)
    # with open(synergys_autostart, 'w') as fp:
    #     fp.write(textwrap.dedent(
    #         """\
    #         [Desktop Entry]
    #         Type=Application
    #         Name=synergys
    #         Exec=/usr/bin/xterm /usr/bin/synergys --enable-crypto --no-daemon
    #         """
    #     ))
    xterm_autostart = os.path.join(autostart_dir, "test-xterm.desktop")
    node.makedirs(autostart_dir, owner=user)
    with open(xterm_autostart, 'w') as fp:
        fp.write(textwrap.dedent(
            """\
            [Desktop Entry]
            Type=Application
            Name=xterm
            Exec=/usr/bin/xterm
            """
        ))

    dotsynergy = os.path.join(synergyhome, ".synergy")
    synergy_pem_path = os.path.join(dotsynergy, "SSL", "Synergy.pem")
    synergy_fprint_local_path = os.path.join(dotsynergy, "SSL", "Fingerprints", "Local.txt")
    synergy_conf_path = os.path.join(synergyhome, ".synergy.conf")
    synergy_pem_contents = "\n".join([synergy_priv_key, synergy_pub_key])
    node.makedirs(f"{dotsynergy}/SSL/Fingerprints", user, 0o0700)
    node.set_file_contents(synergy_pem_path, synergy_pem_contents, owner=user, mode=0o0600)
    node.set_file_contents(synergy_fprint_local_path, synergy_fingerprints_local, owner=user, mode=0o0600)
    shutil.copyfile(module_files.joinpath("synergy.conf"), synergy_conf_path)
    shutil.chown(synergy_conf_path, user=user)
    os.chmod(synergy_conf_path, 0o0644)

    flatpak_overlay = "/psyopsos-data/overlays/var-lib-flatpak"
    if not is_mountpoint("/var/lib/flatpak"):
        node.makedirs(flatpak_overlay, owner="root", group="root", mode=0o0755)
        subprocess.run(["mount", "-o", "bind", flatpak_overlay, "/var/lib/flatpak"])


    if not os.path.exists("/var/lib/flatpak/repo/flathub.trustedkeys.gpg"):
        flathub_gpg = requests.get("https://flathub.org/repo/flathub.gpg", allow_redirects=True)
        with open("/tmp/flathub.gpg", 'wb') as fd:
            fd.write(flathub_gpg.content)
        subprocess.run(
            "flatpak remote-add --gpg-import /tmp/flathub.gpg flathub https://flathub.org/repo/flathub.flatpakrepo",
            shell=True,
            check=True,
        )

    if subprocess.run("flatpak info com.symless.Synergy", shell=True, check=False, capture_output=True).returncode != 0:
        # Synergy isn't installed yet...

        #subprocess.run(["curl", "-o", "/tmp/synergy.flatpak", synergy_flatpak_uri])
        #subprocess.run("flatpak install -y /tmp/synergy.flatpak", shell=True, check=True)
        synergy_flatpak = "/psyopsos-data/roles/synergycontroller/synergy_1.14.4-stable.ad7273eb.flatpak"
        if not os.path.exists(synergy_flatpak):
            # TODO: Download this from Symless automatically
            # I'm not sure how their auth works so right now you have to copy it to this location manually
            # TODO: Maybe just host the Symless flatpak somewhere and sign it with my own key?
            raise Exception(f"Synergy flatpak not downloaded to {synergy_flatpak}, aborting...")

        subprocess.run(f"flatpak install -y {synergy_flatpak}", shell=True, check=True)

    # TODO:
    # Create an openrc script to launch synergyserver flatpak as my user
