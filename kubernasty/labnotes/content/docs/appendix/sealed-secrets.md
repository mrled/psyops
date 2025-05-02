---
title: Encryption with sealed-secrets
---

You could use sealed-secrets instead of [SOPS]({{< ref "sops" >}}).

* Follow the GitOps workflow on [this page](https://fluxcd.io/flux/guides/sealed-secrets/)
  * Add the HelmRepository
  * Add the HelmRelease
  * Push and wait for it to deploy
* Retrieve the keys that were generated in the cluster
  * Save the public key:
    `kubeseal --fetch-cert --controller-name=sealed-secrets-controller --controller-namespace=flux-system > sealed-secrets.pub.pem`
  * Save the private key:
    `kubectl get secret -n flux-system -l sealedsecrets.bitnami.com/sealed-secrets-key > sealed-secrets.key.pem`
    ... save that in a password manager or similar.
