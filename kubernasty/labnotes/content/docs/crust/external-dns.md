---
title: External DNS
weight: 20
---

External DNS lets us define public DNS entries in our Kubernetes configuration,
and has the cluster create those DNS entries via Route53 (or whatever) API when they're applied.

## Create an IAM role with permission to create DNS entries

There are lots of ways to do this;
here's what I do:

* Create a group in {{< repolink "ansible/cloudformation/MicahrlDotCom.cfn.yml" >}}
  called `KubernastyZoneUpdaterGroup` with permissions to update the zone(s).
  See the [external-dns IAM policy example](https://github.com/kubernetes-sigs/external-dns/blob/master/docs/tutorials/aws.md#iam-policy)
  for what permissions this group needs.
* Create a user manually in the AWS console that's a member of that group
* Create access key/secret for the user in the console
* Save the key/secret as creds (see below)

## Configure Route53 credentials

Create a secret with route53 credentials.
This is slightly different in structure to the cert-manager secret,
but (at least for my use case) contains the same credential.
The secret we have to make is in the format of the aws credentials file.
You can make it like this:

```sh
cat > aws.creds.txt <<EOF
[default]
aws_access_key_id = xxxxxxxx
aws_secret_access_key = yyyyyyyy
EOF

credsfile="$(base64 aws.creds.txt -w 0)"

cat > aws-route53-credential.UNENCRYPTED.yaml <<EOF
kind: Secret
apiVersion: v1
type: Opaque
metadata:
  name: external-dns-aws-credential-secret
  namespace: external-dns
data:
  credentials: $credsfile
EOF

sops --encrypt ./aws-route53-credential.UNENCRYPTED.yaml  > aws-route53-credential.yaml
```

{{< details "An annoyed aside" >}}

The docs in the
[external-dns example parameters file](https://github.com/bitnami/charts/blob/main/bitnami/external-dns/values.yaml)
were not clear to me. They say

> ```yaml
> ## AWS configuration to be set via arguments/env. variables
> ##
> aws:
>   ## AWS credentials
>    ## @param aws.credentials.secretKey When using the AWS provider, set `aws_secret_access_key` in the AWS credentials (optional)
>    ## @param aws.credentials.accessKey When using the AWS provider, set `aws_access_key_id` in the AWS credentials (optional)
>    ## @param aws.credentials.mountPath When using the AWS provider, determine `mountPath` for `credentials` secret
>    ##
>    credentials:
>      secretKey: ""
>      accessKey: ""
>      ## Before external-dns 0.5.9 home dir should be `/root/.aws`
>      ##
>      mountPath: "/.aws"
>      ## @param aws.credentials.secretName Use an existing secret with key "credentials" defined.
>      ## This ignores aws.credentials.secretKey, and aws.credentials.accessKey
>      ##
>      secretName: ""
> ```

You'd think you might create a secret object with a `credentials` key containing `secretKey` and `accessKey`, right?
But if you do, that's actually an invalid secret --
secrets can contain only key:value pairs, no nested objects --
and you'll get an error about `unrecognized type: string`.

Upon realizing this, you might think to use `secretKey` and `accessKey` directly,
but this is also wrong.
You will see errors with a command like
`kubectl logs external-dns-7d69b5b986-2cqgj -n external-dns -f --since 10m`,
and they will contain lines like
`time="2023-01-28T05:18:42Z" level=error msg="records retrieval failed: failed to list hosted zones: NoCredentialProviders: no valid providers in chain. Deprecated.\n\tFor verbose messaging see aws.Config.CredentialsChainVerboseErrors"`
.

Instead, you need to set a `data` (not `stringData`!) secret,
with a key called `credentials` that has a value of
_a base64-encoded AWS credentials file_,
as we did above.

Then you have to mount that inside the external-dns container.

This is explained a bit better in the external-dns documentation for AWS.
[Static credentials](https://github.com/kubernetes-sigs/external-dns/blob/master/docs/tutorials/aws.md#static-credentials)
and [Manifest (for clusters without RBAC enabled)](https://github.com/kubernetes-sigs/external-dns/blob/master/docs/tutorials/aws.md#manifest-for-clusters-without-rbac-enabled).
The documentation and most uses of the AWS DNS provider for external-dns
mostly seem to be about using IAM credentials inside an AWS-hosted EKS cluster.
We have to use static credentials because our cluster is bare metal.

{{< /details >}}

Save this as
{{< repolink "kubernasty/manifests/crust/external-dns/aws-route53-credential.example.yaml" >}},
and modify it to contain a real credential.
Then encrypt it with `sops`:

```sh
sops --encrypt kubernasty/manifests/crust/external-dns/aws-route53-credential.example.yaml > kubernasty/manifests/crust/external-dns/aws-route53-credential.yaml
```

**Make sure not to commit any unencrypted credentials files**.

{{< hint warning >}}
**WARNING:**
If you change ever the secret,
including during initial troubleshooting,
you may need to kill the external-dns pod to get it to pick it up.
You can do that by finding the replicaset name with
`kubectl get replicaset -n external-dns`,
and then deleting it with
`kubectl delete replicaset <replica-set-name> -n external-dns`.
Flux will automatically redeploy the replicaset deleted this way,
which will mount your secrets file before starting a new external-dns process,
which will ensure that it picks up the latest.
{{< /hint >}}

## Configure and deploy external-dns

* I followed <https://geek-cookbook.funkypenguin.co.nz/kubernetes/external-dns/>.
* It is also worth looking at the readme for the bitnami external-dns chart at
  <https://github.com/bitnami/charts/tree/main/bitnami/external-dns>.
* The [external-dns documentation for AWS](https://github.com/kubernetes-sigs/external-dns/blob/master/docs/tutorials/aws.md)
  was also helpful, but note that the bitnami chart handles some things for you.
  For instance, specifying `secretName` to the chart the way we did
  handles mounting the credentials file as a volume in the container.

Create {{< repolink "kubernasty/manifests/crust/external-dns/configmaps/configmap-overrides.yaml" >}}.
I also added `configmap.yaml.dist.txt` containing the entirety of the
[external-dns parameters](https://github.com/bitnami/charts/blob/main/bitnami/external-dns/values.yaml).
This way when I'm upgrading external-dns I can diff the defaults I configured previously
and the new version's defaults.
I prefer this to inlining the entire default parameter list into the overrides file
since it makes it much easier to see what I'm trying to configure.

Finally, I add a test DNS record under
{{< repolink "kubernasty/manifests/crust/external-dns/dnsendpoints/test-endpoints.yaml" >}}.
This isn't used except for me to test that everything really is working properly from end to end.

Then commit everything to git, push, and wait for Flux to apply.
