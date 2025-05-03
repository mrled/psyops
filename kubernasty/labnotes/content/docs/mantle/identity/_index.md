---
title: Identity
weight: 50
---

This section covers a lot of related concepts,
including HTTP authentication to restrict users who can access the cluster,
a centralized LDAP directory for all users including service accounts,
etc.

For the account directory,
note that while I **use** [389 Directory Server]({{< ref "389-directory-server" >}})
with my own [LDAPEnforcer]({{< ref ldapenforcer >}}) project,
I **recommend** [LLDAP]({{< ref lldap >}}).

On top of that I put Authelia,
which can control access to different HTTP resources,
act as an OIDC server,
store passkeys for users,
etc

There are many other options in this space of course.
Another one to consider is Authentik,
which can do basically everything that Authelia can do,
and also stores user accounts and can even be an LDAP server for apps that need it.
