# Architect

Personal CI server

## Setup

I wanted to automated this with CloudFormation and Ansible but I got tired of bullshit, so it's half manual. Ugh.

- Create new VM on Linode. (Linode is cheaper than either EC2 or Digital Ocean for 1GB of RAM.)
- Configure root passwords and SSH keys etc
- Install Docker via their official repo
- Install ZeroTier and connect to my network

- Apply firewall

  - Copy `iptables-system.sh` to /etc
  - Make it world -readable -executable: `chmod 755 /etc/iptables-system.sh`

  - Configure the system to run the new iptables script on startup. Edit `/etc/rc.local` to look like this:

      #!/bin/sh
      set -eu
      /etc/iptables-system.sh
      exit 0

    This runs the script, while ensuring (via `set`) that a failing script will result in a nonzero exit code for `rc.local`.

    It is common to put other stuff in `rc.local`; adding extra lines after `set -eu` and before `exit 0` will not hurt anything that we're doing here.

  - Ensure `/etc/rc.local` is executable

- I'm using public DNS for backend infrastructure, so I have `*.infra.micahrl.com` hosts that resolve to private ZeroTier IPv6 addresses

- Install Docker:

  - Follow install instructions: <https://docs.docker.com/engine/installation/linux/docker-ce/debian/#install-using-the-repository>

  - Create the Swarm. (Replace `1.2.3.4` with the address on the ZeroTier interface.)

      docker swarm init --advertise-addr 1.2.3.4

- Docker can have [problems](https://forum.linode.com/viewtopic.php?t=13995&sid=223987b585a4ce92f5186485a2be2990) with the Linode kernels. [Switch to the distro default kernel](https://linode.com/docs/tools-reference/custom-kernels-distros/run-a-distribution-supplied-kernel-with-kvm).
- Use the jenkins.compose.yml file in this directory
- Follow [docs](https://github.com/jenkinsci/docker/blob/master/README.md)
- Grab the initial admin password like `docker exec CONTAINERID cat /var/jenkins_home/secrets/initialAdminPassword`
