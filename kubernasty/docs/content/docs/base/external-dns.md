---
title: External DNS
weight: 70
---

External DNS lets us define public DNS entries in our Kubernetes configuration,
and has the cluster create those DNS entries via Route53 (or whatever) API when they're applied.

See also <https://geek-cookbook.funkypenguin.co.nz/kubernetes/external-dns/>.

Create a secret with route53 credentials.
This is slightly different in structure to the cert-manager secret,
but (at least for my use case) contains the same credential.
It looks like this:

```yaml
kind: Secret
apiVersion: v1
type: Opaque
metadata_unencrypted:
  name: external-dns-aws-credential-secret
  namespace: external-dns
stringData:
  credential:
    accessKey: xxx
    secretKey: yyy
```

Note the slightly different structure compared to the cert-manager secret.
The structure is required by `aws.credentials.secretName` in the
[external-dns example parameters file](https://github.com/bitnami/charts/blob/main/bitnami/external-dns/values.yaml),
which says

> ```yaml
> aws:
>   credentials:
>     ## @param aws.credentials.secretName Use an existing secret with key "credentials" defined.
>     ## This ignores aws.credentials.secretKey, and aws.credentials.accessKey
>     ##
>     secretName: ""
> ```

To be explicit, note the difference between the cert-manager secret:

```yaml
stringData:
  access-key-id: xxx
  secret-access-key: yyy
```

and the external-dns secret:

```yaml
stringData:
  credential:
    accessKey: xxx
    secretKey: yyy
```

Save this as `external-dns/aws-route53-credential.example.yaml`,
and modify it to contain a real credential.
Then encrypt it with our `fluxsops` function from `cluster.sh`:

```sh
fluxsops --encrypt external-dns/aws-route53-credential.example.yaml > external-dns/aws-route53-credential.yaml
```

**Make sure to redact the credential from the unencrypted example file**.

Create `external-dns/configmap-overrides.yaml`.
I also added `configmap.yaml.dist.txt` containing the entirety of the
[external-dns parameters](https://github.com/bitnami/charts/blob/main/bitnami/external-dns/values.yaml).
This way when I'm upgrading external-dns I can diff the defaults I configured previously
and the new version's defaults.
I prefer this to inlining the entire default parameter list into the overrides file
since it makes it much easier to see what I'm trying to configure.

Then commit everything to git, push, and wait for Flux to apply.
