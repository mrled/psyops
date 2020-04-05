# ansible

## Bringing up a network from scratch

1.  Get Internet service and a laptop
1.  Get Ubiquiti gear. Set up the gear from the laptop
1.  Set static IP addresses DNS hostnames for all relevant gear.
	1.  I had to do this with Route53 (public hostname, private IP address) b/c Google Fiber box doesn't support hostnames lol
1.  Get server for unifi controller
    1.  Fedora 29 server
	1.  Get on the network
	1.  Tagasaw specific: configure initial shitty USB wifi controller
	1.  Configure host to meet Ansible requirements (see below)
	1.  Run playbook that handles installing Docker, Docker unifi controller, etc
	1.  Log in to unifi controller, configure passwords, etc
	1.  Adopt unifi gear in the controller
	1.  Install better wifi card
	1.  Tagasaw specific: Run the hardware role to install drivers for new wifi controller
	1.  Tagasaw specific: configure the new USB wifi controller

## General Ansible host requirements

### psyops-ansible@HOST is can passwordless sudo to root

On Fedora:

    useradd --create-home --system --user-group psyops-ansible
    echo 'psyops-ansible ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/psyops-ansible

Also must add psyops public key to the psyops-ansible user.

### Configuring git for ansible-vault

* See the `.gitattributes` file
* See the `.vault-pass-script` file
* Run this on your ansible host: `git config diff.ansible-vault.textconv 'ansible-vault view --vault-password-file ansible/.vault-pass-script'`

This lets diffs in the vault files show as text in `git diff`

## Host specific documentation

### Tagasaw

To connect to my shared LAN `djinnet`

    nmcli con add con-name djinnet ifname wlp0s29u1u7 type wifi ssid djinnet
    nmcli d wifi connect djinnet password "PASSWORD"

To connect to new Ubiquiti AP `nanoton` on nicer PCIe wifi card

    nmcli con add con-name nanoton ifname wlp2s0 type wifi ssid nanoton
    nmcli d wifi connect nanoton password "PASSWORD"

## TODO

* Clear out the fucking firewalld config on every god damned ansible run
  * You can do this by deleting all the zones from /etc/firewalld/zones
  * Is there a less dumb way to do this? Who knows
  * Also don't forget the default zone
  * Probably just reconfigure firewalld from scratch so that it works everywhere
  * Don't forget, some Fedora versions have a default zone like "FedoraServer", for others it's something more generic! Why is this! Please end my life!
