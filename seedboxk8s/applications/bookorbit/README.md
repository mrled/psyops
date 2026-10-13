# BookOrbit

Visit `https://bookorbit.${productionClusterFqdn}` through Authelia. For initial
administrator setup, retrieve the bootstrap token:

```sh
kubectl -n tortuga get secret bookorbit-env -o jsonpath='{.data.SETUP_BOOTSTRAP_TOKEN}' | base64 --decode
```

Create a library at `/media/Books/BookOrbit`, mapped to
`/seedboxmedia/Books/BookOrbit`. The NFS volume is mounted at `/media` without
`subPath`, like Plex and Radarr. The parent directory must be writable by media
UID/GID `6000:6000`.

## SSO

In BookOrbit's OIDC provider settings, enable a provider with:

- **Issuer:** `https://auth.${productionClusterFqdn}`
- **Client ID:** `bookorbit`; **Client secret:** leave empty (public PKCE client).
- **Scopes:** `openid profile email groups`
- **Allow local account linking:** enable for your existing account.

Callback: `https://bookorbit.${productionClusterFqdn}/oauth2-callback`.
Keep local login enabled until SSO works. Authelia's ingress gate stays enabled.
Preserve the encrypted `../authelia/Secret.authelia.yaml` signing secrets.

## Backups

- **Backed up:** BookOrbit `/data` (`bookorbit-config-pvc`) and PostgreSQL dumps
  (`bookorbit-postgres-dump-pvc`).
- **Not backed up:** NFS library storage and live PostgreSQL storage.
- Dumps run daily at **03:00 UTC**, atomically replacing `bookorbit.dump` only
  after success. Staging files are excluded from backup.

See the [PVC restore procedure](../restic-backup/docs/restore.md). Restore `/data`
and import the dump into an empty database using `pg_restore`. Preserve the
original encrypted Secret and its SOPS decryption key.
