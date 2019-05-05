# ansible

## Bringing up a network from scratch

1.  Get Internet service and a laptop
1.  Get Ubiquiti gear. Set up the gear from the laptop
1.  Set static IP addresses DNS hostnames for all relevant gear.
	1.  I had to do this with Route53 (public hostname, private IP address) b/c Google Fiber box doesn't support hostnames lol
1.  Get server for unifi controller
    1.  Fedora 29 server
	1.  Get on the network
	1.  Tagasaw specific: configure wifi controller
	1.  Configure host to meet Ansible requirements (see below)
	1.  Run playbook that handles installing Docker, Docker unifi controller, etc

## General Ansible host requirements

### psyops-ansible@HOST is can passwordless sudo to root

On Fedora:

    useradd --create-home --system --user-group psyops-ansible
    echo 'psyops-ansible ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/psyops-ansible

Also must add psyops public key to the psyops-ansible user.

## Host specific documentation

### Networking on tagasaw

-   To set up my shared LAN, off of the Ubiquiti:

        nmcli con add con-name djinnet ifname wlp0s29u1u7 type wifi ssid djinnet
        nmcli d wifi conneect djinnet password "PASSWORD"
	
-   Then plug in router and AP
-   Run tagasaw playbook to configure Unifi controller software
-   Adopt router and AP in Unifi controller
