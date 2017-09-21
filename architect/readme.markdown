# Architect

Personal CI server

## Setup

I wanted to automated this with CloudFormation and Ansible but I got tired of bullshit, so it's half manual. Ugh.

- Create new VM on Linode

  (Linode is cheaper than either EC2 or Digital Ocean for 1GB of RAM)

- Configure root passwords and SSH keys etc

- Install Docker via their official repo

- Install ZeroTier and connect to my network

- I'm using public DNS for backend infrastructure, so I have `*.infra.micahrl.com` hosts that resolve to private ZeroTier IPv6 addresses

- Docker can have [problems](https://forum.linode.com/viewtopic.php?t=13995&sid=223987b585a4ce92f5186485a2be2990) with the Linode kernels. [Switch to the distro default kernel](https://linode.com/docs/tools-reference/custom-kernels-distros/run-a-distribution-supplied-kernel-with-kvm).

- Use the jenkins.compose.yml file in this directory

- Follow docs https://github.com/jenkinsci/docker/blob/master/README.md

- Grab the initial admin password like `docker exec CONTAINERID cat /var/jenkins_home/secrets/initialAdminPassword`

- NOTE! Docker doesn't support ipv6 very well or something. So honestly use the ipv4 addresses you get with ZeroTier, not the ipv6 ones. Jesus christ man this fucking container software is literally out to get me or something, omw2kms. e.g. https://github.com/moby/moby/issues/24379