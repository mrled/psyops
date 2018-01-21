# Architect

Personal CI server

## Deploying

### Initial deployment

To do the initial AWS deployment,
you'll need to pass parameters specifying secrets,
such as the ipsec configuration for connecting to the VPN.

#### Prerequisites

Configure these items ahead of time.

1.  Install the AWS command line. This is already present in PSYOPS.

2.  Configure the AWS command line with `~/.aws/credentials` and `~/.aws/config`

    NOTE that the rest of this document,
    as well as the configuration in the CloudFormation templates,
    assume that you are using the AWS key and secret for the _root user of the account_.
    If you are instead using an IAM user that does not have root access,
    you should carefully double-check CMK permissions in the `architect.kms.cfn.yaml` template
    to ensure that your IAM user will not be locked out from administering the CMK.

3.  Collect information about our backend infrastructure VPN

    Our backend network for communicating with this server is based on an Algo VPN.
    First we must create a user in your Algo VPN for the Architect server.

    NOTE: we used the name `architect` for our VPN user,
    as configured in Algo's `config.cfg` file.
    If you used a different name,
    substitute it for `architect` below.
    Also note that the `AWS::CloudFormation::Init` section in `architect.cfn.yaml` assumes the user is named `architect`,
    and as such expects `architect.key` and `architect.crt` to be the correct values;
    if a different username was provided, note that the `ipsec_$user.conf` and `ipsec_$user.secrets`
    will expect `.key` and `.crt` files to be named after `$user`.

    Locate the directory that contains the following files:

    - `ipsec_architect.conf`
    - `ipsec_architect.secrets`
    - `architect.p12`


#### Deloying

First, configuration that is dependent on your environment:

    ```sh
    # Set stack names so we can refer to them later
    # These defaults work fine, but feel free to change them if you like
    architect_ci_stack="ArchitectCi"
    architect_kms_stack="ArchitectKms"

    # The path to the algo repository's config/ subdir
    configpath="/path/to/algo/config"

    # The p12 password, from Algo's output after deployment
    # (This example value must be changed for your environment)
    pkcs12pass="ohd6uoP5"
    ```

Now, use that configuration to deploy:    

    ```sh
    # Deploy the KMS and an IAM role that can use the KMS
    # We have to supply the --capabilities flag
    # because modifying IAM roles can affect the entire AWS account
    # and Amazon restricts this unless you explicitly allow it
    aws cloudformation deploy \
        --capabilities CAPABILITY_NAMED_IAM \
        --template-file ./architect.kms.cfn.yaml \
        --stack-name "$architect_kms_stack"

    # Get the ID of the KMS that we are using
    kmsquery='Stacks[0].Outputs[?OutputKey==`ArchitectKmsId`].OutputValue'
    kmsid=$(aws cloudformation describe-stacks --stack-name "$architect_kms_stack" --query "$kmsquery" --output text)

    # Get the name of the instance profile for the Architect EC2 instance
    profquery='Stacks[0].Outputs[?OutputKey==`ArchitectInstanceIamProfileName`].OutputValue'
    profname=$(aws cloudformation describe-stacks --stack-name "$architect_kms_stack" --query "$profquery" --output text)

    # Convert the PKCS12, which contains both private key + public cert, into separate key/cert values
    vpnkey=$(openssl pkcs12 -in "$configpath/architect.p12" -nocerts -passin pass:$pkcs12pass -nodes)
    vpncrt=$(openssl pkcs12 -in "$configpath/architect.p12" -clcerts -nokeys -passin pass:$pkcs12pass)

    # Encrypt the now-passwordless PEM cert using your newly created AWS KMS
    vpnkey_encrypted=$(aws kms encrypt --key-id "$kmsid" --plaintext "$vpnkey" --query 'CiphertextBlob' --output text)
    # NOTE: the result of this command is binary data that has been base64 encoded
    # To decrypt it from the KMS, you must decode it from base64 first:
    #   vpnkey_encrypted_decoded=$(echo "$vpnkey_encrypted" | base64 -d)
    #   aws kms decrypt --ciphertext-blob "$vpnkey_encrypted_decoded"

    # Once that configuration is done, this can be copied and pasted
    aws cloudformation deploy \
        --template-file ./architect.cfn.yaml \
        --stack-name "$architect_ci_stack" \
        --parameter-overrides \
            Ec2InstanceProfileName="$profname" \
            VpnIpsecUserConf="$(cat "$configpath/ipsec_architect.conf")" \
            VpnIpsecUserSecrets="$(cat "$configpath/ipsec_architect.secrets")" \
            VpnKeyEncrypted="$vpnkey_encrypted" \
            VpnCert="$vpncrt" \
            KmsId="$kmsid"
    ```

#### Connecting over SSH for troubleshooting

The stack output contains the IP address,
and you can retrieve it with the command:

    ```sh
    ipquery='Stacks[0].Outputs[?OutputKey==`ArchitectIpAddress`].OutputValue'
    aws cloudformation describe-stacks --stack-name "$architect_ci_stack" --query "$ipquery" --output text
    ```

After the very first boot,
you can obtain the host key like this:

    ```sh
    iidquery='Stacks[0].Outputs[?OutputKey==`ArchitectInstanceId`].OutputValue'
    iid=$(aws cloudformation describe-stacks --stack-name "$architect_ci_stack" --query "$iidquery" --output text)
    aws ec2 get-console-output --output text --instance-id "$iid"
    ```

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

#### Troubleshooting tips

View userdata (from the instance itself)

    ```sh
    wget -q -O - http://169.254.169.254/latest/user-data
    ```

If the `cfn-init` command is failing,
comment out the `cfn-init` invocation in userdata,
deploy the stack,
run the command manually the same way it would be run by userdata,
and then check logs at `/var/log/cfn-*.log`.

You can also use the `cfn-get-metadata` command to see the `AWS::CloudFormation::Init` metadata from the template.
You can find the call to `cfn-init` in the CloudFormation template,
and then replace `cfn-init` with `cfn-get-metadata` to see the metadata exactly as `cfn-init` would.
For example:

    ```sh
    # The cfn-init call from userdata:
    cfn-init -v --stack "$stackname" --resource ArchitectInstance --region "$region"
    # Call cfn-get-metadata instead:
    cfn-get-metadata -v --stack "$stackname" --resource ArchitectInstance --region "$region"
    ```

### Subsequent deployments

To redeploy later,
it is enough to just specify the template file and stack name arguments;
unless the template parameters have changed,
there is no need to supply parameter overrides during a redeployment.

