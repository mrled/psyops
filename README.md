# psyops: Personal SYs OPS

Shit I use to manage my own infrastructure

Directories:

- .claudebox: Configuration for claudebox2 script from submod/dhd repository
- ansible: infrastructure as code
  - tagasaw seedbox running seedboxk8s single-node Kubernetes cluster
  - dreadnaught chineseroom host for AI agent containment
  - apsylania server running misc services, including hosting for Tor hidden services that mirror me.micahrl.com
  - wenaglia TailScale exit note and out of state SOCKS proxy
  - bolgana IRC bouncer running The Lounge
  - CloudFormation templates for DNS (micahrl.com, micahrl.me, younix.us, seedbox domain)
- docker: Mostly deprecated interactive container that provides a host-OS-independent container to use this psyops; ignore
- fly: Deploy fly.io infrastructure
  - disagreements.micahrl.com: the comments engine for my blog at https://me.micahrl.com
- kubernasty: a multi-node homelab Kubernetes cluster
- seedboxk8s: a single-node homelab Kubernetes cluster
  - Runs on tagasaw baremetal host
  - Runs apps for media downloading and playback, including Plex, *arr apps, sabnzbd, etc.
  - k0s Kubernetes runtime
  - flux CI/CD
- lima: Lima VMs for macOS, including dreadnaught, which is a chineseroom VM for agent containment
- pipelines: CI / data pipeline definitions
- progfiguration_blacksite: infrastructure-as-code site package
  - Uses the generic root progfiguration pacakge in submod/progfiguration
  - Deploys kubernasty bare metal nodes,
- psyopsOS: an Alpine Linux -based netbooting OS which runs on kubernasty bare metal nodes
- submod: various dependencies, including
  - dhd: distributed home directory: personal config files
  - progfiguration: a custom infrastructure-as-code system written in Python.
- telekinesis: Python package that builds various parts of this repo, especially psyopsOS
- terraform: Terraform IaC files; mostly deprecated
- unifi-setup: scripts I copy to Unify hardware manually
