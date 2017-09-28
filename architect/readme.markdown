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

## TLS certificate for Jenkins with Let's Encrypt

My Jenkins server is on a private network with no public access, but it does have a public DNS name. (The public DNS name resolves to a `192.168.x.x` IP address.) This makes what appears to be the simplest way to use Let's Encrypt, an HTTP challenge where the ACME server connects to your HTTP server and requests a particular file, impossible. Instead, we want to use a DNS challenge, where we set a special DNS record and the ACME server reads it to verify the challenge.

My DNS server (and registrar) is Gandi, so that's what's used below. Many other DNS providers are widely supported by several different ACME clients, so if you use a different provider, make sure you find a client that supports your provider. Gandi is *not* as widely supported as more popular DNS services; if you're shopping for DNS service, you may wish to use something more widespread, such as Route53, which appears to have support in basically any ACME client that supports DNS challenges.

I'm using the [lego](https://github.com/xenolf/lego) ACME client, even though it says it's alpha, because it supports Gandi and because the developer publishes a convenient Docker image (`xenolf/lego`) to the Docker store.

### Generating the certificate

Before automating it, you'll need to run it manually first:

    letsencrypt_email="some email address"
    domain="jenkins.example.com"
    gandi_api_key="yourapikey"
    lego_volume="$HOME/lego"
    mkdir -p "$lego_volume"
    docker run \
        --rm \
        --interactive \
        --tty \
        --env "GANDI_API_KEY=$gandi_api_key" \
        --volume "${lego_volume}:/.lego" \
        xenolf/lego \
            --accept-tos \
            --email "$letsencrypt_email" \
            --domains "$domain" \
            --dns gandi \
            run

This command will configure a Let's Encrypt account, create a private key, request that the ACME server signs the private key, and asks the ACME server to verify ownership by a DNS challenge, using Gandi's API to set and delete the challenge record. It will save the Let's Encrypt account info and public/private TLS keys to the `$legovolume` directory.

When I ran this, it took about 30 minutes.

### Using the certificate with Jenkins

Some references:

- <https://stackoverflow.com/questions/29755014/setup-secured-jenkins-master-with-docker>
- <https://github.com/hughperkins/howto-jenkins-ssl/blob/master/letsencrypt.mde>

Once the certificate is generated, you must configure Jenkins to use it. Copy the public and private keys to the directory being mounted as the `/var/jenkins_home` volume in the Jenkins Docker image.

    cp "$domain.crt" "$domain.key" /path/to/jenkins_home
    docker run -v /path/to/jenkins_home:/var/jenkins_home -p 443:8443 jenkins --httpPort=-1 --httpsPort=8443 --httpsCertificate="/var/jenkins_home/$domain.crt" --httpsPrivateKey="/var/jenkins_home/$domain.key"
