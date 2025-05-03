---
title: 389 Directory Server
weight: 40
---

I have built an enjoyably overengineered deployment process for
[389 Directory Server](https://www.port389.org/).

(The *easiest* thing to do is use [LLDAP]({{< ref "lldap" >}}),
but that's not as fun.
I will stress that it is _much easier_.)

The fun part is in
{{< repolink "kubernasty/applications/directory/dirsrv/ConfigMap.initldifs" >}},
which contain `.ldif` files applied by scripts in
{{< repolink "kubernasty/applications/directory/dirsrv/ConfigMap.initsetup" >}}.
The application of these files is made idempotent by the
`apply_marked_ldif.sh` script,
where a special OU is checked before applying each LDIF;
if there is an object in the OU for the LDIF, it is skipped,
but if not, it is applied and the object is created.
This prevents an LDIF of the same name from being applied again,
and it works like some database migrations systems work.
I also wrote a [blog post](https://me.micahrl.com/blog/ldap-migrations/)
on this subject.

## Creating users and groups, and applying group membership

tl;dr: add an LDIF in
{{< repolink "kubernasty/applications/directory/dirsrv/ConfigMap.initldifs" >}}.

Understand the difference between POSIX users/groups and LDAP users/groups.
An LDAP group may also be a POSIX group;
LDAP and POSIX membership are tracked via separate attributes,
such that its possible for a user to be an LDAP but not POSIX member of the same group (or vice versa).
Most groups can be LDAP groups and do not need to be POSIX groups;
only in cases where a user could log in via ssh or something
would the POSIX user/group matter.

There's no way to do transitive group membership,
such that the `serviceadmins` group contains the `admins` group,
and `myadmin` is a member of `admins` and therefore automatically a member of `serviceadmins`.
This doesn't work.
You just have to make the same user a member of both groups if that's what you want.

## Interacting with the LDAP server

I use the `ldap*` commands.
The easiest way to use them is to make aliases that run them in the sidecar,
which I've done in
{{< repolink "kubernasty/cluster.sh" >}}:

```sh
# Some convenience aliases for talking to the LDAP server
# Include auth for each command,
# and set some options where appropriate.
alias kldapsearch='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldapsearch -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password -LLL -o ldif-wrap=no'
alias kldapmodify='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldapmodify -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password'
alias kldapadd='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldapadd -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password'
alias kldapdelete='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldapdelete -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password'
alias kldappasswd='kubectl exec -itn directory dirsrv-0 -c configurator -- /bin/ldappasswd -H ldaps://dirsrv:636 -D "cn=Directory Manager" -y /containeripc/topsecret/ds-dm-password'

# Convenience commands for dealing with the LDAP markers (migrations)
kldif_list_markers() {
    kldapsearch -s one -b "ou=ldifMarkers,dc=micahrl,dc=me" "(objectClass=*)" dn |
        grep -v '^\s*$' |
        sort
}
kldif_delete_marker() {
    filename="$1"
    kldapdelete "cn=$filename,ou=ldifMarkers,dc=micahrl,dc=me"
}
alias kldif_list_files='kubectl exec -it -n directory dirsrv-0 -c configurator -- sh -c "ls -a1 /initldifs/*.ldif"'
alias kldif_apply='kubectl exec -it -n directory dirsrv-0 -c configurator -- /initsetup/apply_ldifs.sh'
kldif_cat() {
    filename="$1"
    kubectl exec -it -n directory dirsrv-0 -c configurator -- cat "/initldifs/$filename"
}
```

I set up LDAP Account Manager, but I don't really like it and never use it.

## Future

It's a little too verbose.
I'd like to make a simple system where user/group membership is tracked in flat files
which can be applied idempotently.
This probably wouldn't replace the LDIF system,
but complement it for more general user/group management.
