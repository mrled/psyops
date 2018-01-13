# Architect

Personal CI server

## Deploying

### Initial deployment

To do the initial AWS deployment,
you'll need to pass parameters specifying secrets,
such as the ipsec configuration for connecting to the VPN.

#### Prerequisites

Configure these items ahead of time.

Our backend network for communicating with this server is based on an Algo VPN.

1. Create a user in your Algo VPN for the Architect server (we will use the token `$user` to refer to the name of this user)

2. Find the `ipsec_$user.conf` file

3. Find the `ipsec_$user.secrets` file

4. Convert the `$user.p12` file from PKCS12 to PEM format with OpenSSL:

        openssl pkcs12 -in $user.p12 -nocerts -out $user.key
        openssl pkcs12 -in $user.p12 -clcerts -nokeys -out $user.cert

#### Deloying

    # Configure these things ahead of time
    configpath="/path/to/algo/vpn/files"
    vpn_pkcs12_passphrase="passphrase for the algo VPN PKCS12 certificate"

    # Once that configuration is done, this can be copied and pasted
    aws cloudformation deploy \
        --template-file ./architect.cfn.yaml \
        --stack-name architect \
        --parameter-overrides \
            VpnIpsecUserConf="$(cat $configpath/ipsec_architect.conf)" \
            VpnIpsecUserSecrets="$(cat $configpath/ipsec_architect.secrets)" \
            VpnUserCert="$(cat $configpath/architect.p12 | base64)" \
            VpnUserKey=XXX

#### Troubleshooting

The stack output contains the IP address,
and you can retrieve it with the command:

    aws cloudformation describe-stacks --stack-name <STACK NAME>

After the very first boot,
you can obtain the host key like this:

    aws ec2 get-console-output --output text --instance-id <INSTANCE ID>

**Note that this only works after the very first boot.**
Subsequent boots will not display the host key.
I hope you got it after the first one!

(In practice,
this isn't too bad,
because the Cloud Formation template automatically connects the system to our VPN,
and MITM attacks are not a problem if we can trust the VPN;
this is only really useful when trying to modify,
and debug problems with,
an initial deployment.)

You also must obtain the IP address of the EC2 instance,
which you can obtain from the AWS console or the template's `ArchitectIpAddress` output.

Once the host key is verified,
simply use whatever SSH key pair is associated with the instance -
that is,
whatever key pair was specified by the `KeyName` parameter to the CFN template.
In the example below,
I also supply `-o UserKnownHostsFile=/dev/null` on the command line,
which prevents ssh from saving the host key to `~/.ssh/known_hosts`
on the SSH client machine.

    ssh -o UserKnownHostsFile=/dev/null admin@<IP ADDRESS> -i /path/to/keypair.pem

### Subsequent deployments

To redeploy later,
it is enough to just specify the template file and stack name arguments;
unless the template parameters have changed,
there is no need to supply parameter overrides during a redeployment.

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

        `lego` can take 20-30 minutes to validate the DNS challenge
        and receive the signed certificate from Let's Encrypt.
        During this time, the `jenkins` image will come up,
        see that it cannot find its TLS certificates,
        and shut back down,
        but once the certificates are available,
        it will stay up.

        Track this process by following the logs for the `inflatable-wharf` service
        (see below).

     -  You can view logs it by first getting service IDs:

            docker stack services jenkins

        Which might return output like this:

            ID                  NAME                       MODE                REPLICAS            IMAGE                           PORTS
            uvafm36cyz38        jenkins_jenkins            replicated          1/1                 jenkins/jenkins:lts             *:80->8080/tcp,*:443->8443/tcp
            vla3440dmlwn        jenkins_inflatable-wharf   replicated          1/1                 mrled/inflatable-wharf:latest   

        And then grabbing the log for the service in question based on that service ID:

            # The -f argument to logs works like the -f argument to tail,
            docker service logs -f uvafm36cyz38

        (Note that `docker service logs` operates on _service_ IDs you get from `docker stack services`,
        not _container_ IDs that you might get from `docker ps`)

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

## Troubleshooting

This command will use the `lego` container to connect to the _staging_ API endpoint,
configure a Let's Encrypt account,
create a private key,
request that the ACME server signs the private key,
and ask the ACME server to verify ownership by a DNS challenge,
using Gandi's API to set and delete the challenge record.
It will save the Let's Encrypt account info
and public/private TLS keys to the `$legovolume` directory.

When I ran this, it took about 30 minutes.

    letsencrypt_email="some email address"
    domain="jenkins.example.com"
    gandi_api_key="yourapikey"
    lego_volume="$(pwd)/lego-temp-volume"
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
            --server "https://acme-staging.api.letsencrypt.org/directory" \
            run

Some references:

- <https://stackoverflow.com/questions/29755014/setup-secured-jenkins-master-with-docker>
- <https://github.com/hughperkins/howto-jenkins-ssl/blob/master/letsencrypt.md>
