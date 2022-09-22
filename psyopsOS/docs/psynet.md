# Nebula backchannel network

There is a backchannel network for _all_ psyopsOS nodes.

- `10.10.8.0/22` (`10.10.8.0`-`10.10.11.255`) is the total network
- `10.10.8.0/24` (`10.10.8.1`-`10.10.8.255`) is reserved for lighthouses
- `10.10.9.0/24` (`10.10.9.1`-`10.10.9.255`) is reserved for non-psyopsOS nodes, clients like my laptop and phone
- `10.10.10.0/23` (`10.10.10.1`-`10.10.11.255`) is reserved for psyopsOS nodes

We use some base groups.
In the future, some nodes (which may or not run psyopsOS) might define app-specific groups.

- `clients` is for my personal laptop, phone, etc and have access to any host in the network
- `lighthouses` is just the lighthouses and has access to no hosts in the network, except by ICMP
- `psyopsOS` is for psyopsOS nodes

Nodes should be added to the `ansible/cloudformation/PsynetZone.cfn.yml` file for Route53 DNS entries.

## Bootstrap process

```sh
# Create the Nebula CA
# We set it to 100 years because nobody has time for fucking key rotation, gtfo lol
nebula-cert ca -duration 876000h -name "Psynet Nebula Certificate Authority"
# Lighthouses. We create their certificates before starting their VMs.
nebula-cert sign -name lighthouse1 -ip 10.10.8.1/22 -groups lighthouses
nebula-cert sign -name lighthouse2 -ip 10.10.8.2/22 -groups lighthouses
```

This resutls in `ca.key` and `ca.crt` for the certificate authority,
`lighthouse1.key` and `lighthouse1.crt` for the first lighthouse,
etc.

## Adding nodes

psyopsOS nodes will be created in the same way as the clients, and belong to the `psyopsOS` group.
(See also [System secrets and individuation](./system-secrets-individuation.md).)
psyopsOS brings up psynet automatically when it boots.

For client nodes, we don't mind a more manual solution.

### macOS client nodes

I did something like this for my laptop.

```sh
# Laptop
nebula-cert sign -name haluth -ip 10.10.9.1/22 -groups clients
```

Then we want to install it as a launchd service.
(Thanks to [Eliseo](https://eliseomartelli.it/blog/nebula) for this.)

- Download the `nebula` binary and copy to `/usr/local/bin/nebula`
- Create the launchd plist (see below) and copy to `/Library/LaunchDaemons/com.micahrl.psynet.plist`
- Create the Nebula config file (see below) and copy to `/usr/local/etc/nebula/config.yaml`
- Load the new plist with `sudo launchctl load /Library/LaunchDaemons/com.micahrl.psynet.plist`

#### `com.micahrl.psynet.plist` launchd config file

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
      <key>Label</key>
      <string>/usr/local/bin/nebula</string>
      <key>ProgramArguments</key>
      <array>
          <string>/usr/local/bin/nebula</string>
          <string>-config</string>
          <string>/usr/local/etc/nebula/config.yaml</string>
      </array>
      <key>RunAtLoad</key>
      <true/>
  </dict>
</plist>
```

#### `config.yaml` Nebula config file

```yaml
pki:
  ca: |
    -----BEGIN NEBULA CERTIFICATE-----
    ClUKI1BzeW5ldCBOZWJ1bGEgQ2VydGlmaWNhdGUgQXV0aG9yaXR5KInVopkGMImR
    g/kROiAKeLG60P8iFoZPnSpeHXkYEVVo0uvpwehrKjNl8zhdkkABEkB2X0G/HD42
    HkOqFFkIrw/uGjVinBeHEcSkUspQ3BR14JdGH5rvp3DWG6MOEknIrxobNOg2ze4N
    PpphjeozxBsB
    -----END NEBULA CERTIFICATE-----
  cert: |
    -----BEGIN NEBULA CERTIFICATE-----
    CnYKBmhhbHV0aBIJgZKoUID4//8PIgdjbGllbnRzIghwc3lvcHNPUyjI4KKZBjCI
    kYP5ETogAZsXFACEz+y2+5ouBCsHnVI4VoNmhDEluctKwKQZ/mVKIItczbWM0xJ3
    Y+zsSf/l0216px91N4dGLnz9qFXSAPA7EkAfGU1x/+TQwlWxGqUFKjn5/yXNNhuj
    aM5XX0mVtKD63yBPnFkzt++kMHClXjexK3H95NMNltB11uhGJ3CsKNQO
    -----END NEBULA CERTIFICATE-----
  key: |
    -----BEGIN NEBULA X25519 PRIVATE KEY-----
    <REDACTED>
    -----END NEBULA X25519 PRIVATE KEY-----

static_host_map:
  "10.10.8.1": ["134.122.122.82:4242"]
  "10.10.8.2": ["137.184.44.46:4242"]

lighthouse:
  hosts:
    - "10.10.8.1"
    - "10.10.8.2"

punchy:
  punch: true

tun:
  # For macOS: if set, must be in the form `utun[0-9]+`.
  #dev: utun69
  drop_local_broadcast: false
  drop_multicast: false
  tx_queue: 500
  mtu: 1300
  routes:
  unsafe_routes:

firewall:
  conntrack:
    tcp_timeout: 120h
    udp_timeout: 3m
    default_timeout: 10m
    max_connections: 100000

  outbound:
    - port: any
      proto: any
      host: any

  inbound:
    # Allow ICMP from any node, including lighthouses
    - port: any
      proto: icmp
      host: any
    # Allow other members of the `clients` group to access us, but no other nodes.
    - port: any
      proto: any
      groups:
        - clients
```

### iOS client nodes

To get this on my phone (iOS), I had to:

- Generate the key on my phone in the Nebula app. It only shows the public key, and will not export the private key.
- Copy the public key to my Nebula CA machine as `copland.pub`
- Sign that public key with `nebula-cert sign -in-pub copland.pub -name copland -ip 10.10.9.2/22 -groups clients`
- (You can also use `-out-qr copland.qr.png` to make the next two steps easier.)
- Copy the resulting `copland.crt` back to the Nebula app and click "Load certificate"
- I also had to copy the contents of `ca.crt` (NOT the private `ca.key`) to the iOS app, and configure static hosts for the lighthouses

You can examine the generated config in the app,
which creates it in the same YAML format used on other operating systems.
Note that inbound firewall rules are not defined,
and since Nebula is default-deny for fireawll rules,
this means that iOS clients are not accessible from other nodes.

## Booting lighthouses

- Deploy the instances with Terraform in `terraform/psynet-lighthouse` in the root of this repo.
- Add the new instances to the Ansible inventory in `ansible` in the root of this repo
- Generate key/cert for each instance and add to their vault under `ansible/inventory/<hostname>/vault.yml`
- Run this role with the `ansible/_psynet_lighthouses.yml` playbook
