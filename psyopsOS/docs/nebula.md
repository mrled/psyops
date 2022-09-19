# Nebula backchannel network

There is a backchannel network for _all_ psyopsOS nodes.

- `10.10.8.0/22` (`10.10.8.0`-`10.10.11.255`) is the total network
- `10.10.8.0/24` (`10.10.8.1`-`10.10.8.255`) is reserved for lighthouses
- The remainder is for nodes

## Bootstrap process

```sh
# Create the Nebula CA
nebula-cert ca -name "psyopsOS Nebula Certificate Authority"
# Lighthouses. We create their certificates before starting their VMs.
nebula-cert sign -name lighthouse1 -ip 10.10.8.1/22
nebula-cert sign -name lighthouse2 -ip 10.10.8.2/22
# Nebula hosts. We need one for client devices, as well as one for each psyopsOS node.
# Create a couple of default client devices here.
nebula-cert sign -name haluth -ip 10.10.9.1/22 -groups clients,psyopsOS
```

This resutls in `ca.key` and `ca.crt` for the certificate authority,
`lighthouse1.key` and `lighthouse1.crt` for the first lighthouse,
etc.

psyopsOS nodes will be created in the same way as the clients, and belong to the `psyopsOS` group.
(See also [System secrets and individuation](./system-secrets-individuation.md).)

## Booting lighthouses

- Deploy the instances with Terraform in `terraform/psynet-lighthouse` in the root of this repo.
- Add the new instances to the Ansible inventory in `ansible` in the root of this repo
- Generate key/cert for each instance and add to their vault under `ansible/inventory/<hostname>/vault.yml`
- Run this role with the `ansible/_psynet_lighthouses.yml` playbook
