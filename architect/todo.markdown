# Architect bugs and to do list

## Rewrite old readme

The old readme described more things, but it was using Digital Ocean.

As I learn how to do those things, add them to the current version of the readme, and delete them from here.

What remains to be translated into AWS from the old readme: 

    ## Remaining tasks

    This is stuff from the previous incarnation (more manual, and deployed to Linode). I need to assimilate these into the latest incarnation (more automatic, and deployed to AWS).

    -  Configuring StrongSwan VPN

    -  Apply firewall

        -  Copy `iptables-system.sh` to /etc

        -  Make it world -readable -executable: `chmod 755 /etc/iptables-system.sh`

        -  Configure the system to run the new iptables script on startup. Edit `/etc/rc.local` to look like this:

                #!/bin/sh
                set -eu
                /etc/iptables-system.sh
                exit 0

            This runs the script, while ensuring (via `set`) that a failing script will result in a nonzero exit code for `rc.local`.

            It is common to put other stuff in `rc.local`; adding extra lines after `set -eu` and before `exit 0` will not hurt anything that we're doing here.

        -  Ensure `/etc/rc.local` is executable

    -  I'm using public DNS for backend infrastructure, so I have `*.infra.micahrl.com` hosts that resolve to private ZeroTier IPv6 addresses

    -  Create the Docker Swarm. (Replace `1.2.3.4` with the address on the VPN interface.)

                docker swarm init --advertise-addr 1.2.3.4

    -  Configure `docker-machine` on your workstation

        In my case, I used the following to create the `docker-machine` entry
        for the Docker host that will run my Jenkins server:

            docker-machine create --driver generic --generic-ip-address architect.infra.micahrl.com --engine-storage-driver overlay2 architect

        This step is only necessary once (per workstation)

        -  During troubleshooting, running `docker-machine -D create ...` provides more debugging information.

        -  I had to pass the `--engine-storage-driver overlay2` argument
            because it was using `aufs` by default,
            which was preventing the Docker daemon on architect from starting
            after running `docker-machine create`.
            [See also](https://github.com/docker/machine/issues/4197).

    -  Configure `docker` to interact with the remote machine:

            eval $(docker-machine env architect)

        This step is run once per shell that you wish to use to interact with the remote Docker host

    -  Set the necessary environment variables in `lego-acme-secret-env.txt`.

        Mine looks like this:

            GANDI_API_KEY=xxx

    -  Ensure the compose file contains correct values

        -  Ensure the `DOCKER_HOST_DOCKER_GID` variable matches the GID for the `docker` user on your docker host.
        -  Ensure the paths to the HTTPS certificates are correct
            (they're based on the domain name you give to Let's Encrypt)
        -  Provide the correct variables to `inflatable-wharf` for your environment

    -  Deploy the jenkins.compose.yml file in this directory

            docker stack deploy --compose-file jenkins.compose.yml  jenkins

        -  This spins up an an official `jenkins` image,
            and also an `inflatable-wharf` image that handles certificate renewal
            via the `lego` Let's Encrypt client.

            **Jenkins will not be available until `lego` has received the signed certificate from Let's Encrypt**

         -  For more information on how `inflatable-wharf` works,
            including troubleshooting steps and how to view logs,
            see <https://github.com/mrled/inflatable-wharf>

    -  Follow [docs](https://github.com/jenkinsci/docker/blob/master/README.md)

    -  Grab the initial admin password from the `jenkins` service's logs (see above)

    ## Let's Encrypt notes

    My Jenkins server is on a private network with no public access, but it does have a public DNS name. (The public DNS name resolves to a `192.168.x.x` IP address.) This makes what appears to be the simplest way to use Let's Encrypt, an HTTP challenge where the ACME server connects to your HTTP server and requests a particular file, impossible. Instead, we want to use a DNS challenge, where we set a special DNS record and the ACME server reads it to verify the challenge.

    My DNS server (and registrar) is Gandi, so that's what's used below. Many other DNS providers are widely supported by several different ACME clients, so if you use a different provider, make sure you find a client that supports your provider. Gandi is *not* as widely supported as more popular DNS services; if you're shopping for DNS service, you may wish to use something more widespread, such as Route53, which appears to have support in basically any ACME client that supports DNS challenges.

    During troubleshooting,
    it's recommended that you use the [Let's Encrypt staging server](https://letsencrypt.org/docs/staging-environment/),
    so that you don't exhaust the fairly restrictive limits
    for the Let's Encrypt production environment.

    I'm using the [lego](https://github.com/xenolf/lego) ACME client,
    even though it says it's alpha,
    because it supports Gandi
    and because the developer publishes a convenient Docker image (`xenolf/lego`) to the Docker store.
    Below, we use the image that the developer pushed directly;
    in the Docker compose file,
    we use an image derived from that image called [inflatable-wharf](https://github.com/mrled/inflatable-wharf).

    ## References

    - <https://stackoverflow.com/questions/29755014/setup-secured-jenkins-master-with-docker>
    - <https://github.com/hughperkins/howto-jenkins-ssl/blob/master/letsencrypt.md>

