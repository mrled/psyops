---
title: Migrating applications between kustomizations
---

{{% hint warning %}}
Remember, there are [two kustomization types]({{< ref two-kustomization-types >}}). This page discusses the Flux kustomization type.
{{% /hint %}}

You can migrate an app between Flux kustomizations ---
that is, from being deployed by one kustomization to another ---
without any downtime.

Assume that an `old-kustomization` already exists,
and has a path of `/kubernasty/applications/oldlocation/someapp`.
Create a `new-kustomization` that has a path of `/kubernasty/applications/newlocation`
if it doesn't already exist.

```sh
old=old-kustomization
new=new-kustomization

# Suspend the old one so it doesn't apply any changes
flux suspend kustomization $old
# Prevent changes or deletions from tearing down resources
kubectl patch kustomization $old --type=merge -p '{"spec":{"prune":false}}'
```

Now move `someapp` from the old place to the new place,
Make sure to delete references from the old place and add them in the new place.
For instance,
if there was `oldlocation/kustomize.yaml` that referenced `someapp/some-resources.yaml`,
delete that there and put it in `newlocation/kustomize.yaml`.

Then:

```sh
git add .
git commit -m "Move someapp from oldlocation to newlocation"
git push
```

Watch the `new-kustomization` resource in Flux to see when it is fully reconciled with this change.

```text
> k get kustomization -n flux-system new-kustomization
NAME                AGE   READY   STATUS
new-kustomization   57d   True    Applied revision: master@sha1:96a04a784ac7597d84f79bc9927b3e4f7557b106
```

Once that's done, you can resume the old one.
(It's very important that the patch command was run previously.)

```sh
flux resume kustomization $old
```

This also works if you just want to delete the old one.
