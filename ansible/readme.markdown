# ansible

## Configuring git for ansible-vault

- See the `.gitattributes` file
- See the `.vault-pass-script` file
- Run this on your ansible host: `git config diff.ansible-vault.textconv 'ansible-vault view --vault-password-file ansible/.vault-pass-script'`

This lets diffs in the vault files show as text in `git diff`

## How to manage Route53 zones and updaters

This way I can manage DNS in Route53,
and use ACME updaters (like traefik, or certbot)
and only give credentials that allow updating one zone to the updater.

- Make a new zone by adding a CloudFormation template to `cloudformation`
- In the CFN template, make a group that has permission to update the zone,
  and return the Zone ID and group ARN
- Add the new template to the `dns.yml` playbook
- Deploy it
- Find the DNS servers in the AWS console and configure them in the DNS registrar
- Note the newly created zone ID and group ARN
- Create a new IAM user in the new zone updater group -- just do this manually in the aws console
- Save the access/secret keys from the new IAM user into the vault
- Then reference the vault access/secret keys as well as the created zone ID when deploying your ACME updater

## Playbooks

Playbooks are prefixed with a single underscore (`_`), which keeps them nicely organized in my list.

Playbooks that call other playbooks are sometimes useful too; these are prefixed with a double underscore (`__`).
