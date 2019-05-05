# ansible

## Ansible host requirements

### psyops-ansible@HOST is can passwordless sudo to root

On Fedora:

	useradd --create-home --system --user-group psyops-ansible
	echo 'psyops-ansible ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/psyops-ansible

Also must add psyops public key to the psyops-ansible user.

## Original network setup

- Hosts available on the local network
- DNS configured somehow? I guess by hardcoded DHCP entries and public Route53 DNS entries.

### Networking on tagasaw

-   To set up my shared LAN, off of the Ubiquiti:

        nmcli con add con-name djinnet ifname wlp0s29u1u7 type wifi ssid djinnet
        nmcli d wifi conneect djinnet password "PASSWORD"
	
-   Then plug in router and AP
-   Run tagasaw playbook to configure Unifi controller software
-   Adopt router and AP in Unifi controller
