---
title: DNS
weight: 10
---

You'll need a DNS server that you have full programmatic control over, like a Route53 zone.
Make sure the provider is supported by cert-manager.

I use a public DNS zone `micahrl.me` hosted in Route53
with wildcard subdomains pointing to the cluster's VRRP IP.
A subdomain like `cluster.example.com` is fine.

I handle this in CloudFormation under {{< repolink "ansible/cloudformation/MicahrlDotCom.cfn.yml" >}}.

{{% hint info %}}
You can have a wildcard for a domain that also has other subdomains;
e.g. if you're using `asdf.example.com` and `qwer.example.com`,
you can still create a wildcard `*.example.com`
to indicate all other subdomains.
{{% /hint %}}

Kubernetes can create DNS entries for you if you like,
using something like [external-dns](https://github.com/kubernetes-sigs/external-dns).
