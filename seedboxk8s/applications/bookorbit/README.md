# BookOrbit

## First deployment

1. Deploy the apps
2. Retrieve the bootstrap token:
   ```sh
   kubectl -n tortuga get secret bookorbit-env -o jsonpath='{.data.SETUP_BOOTSTRAP_TOKEN}' | base64 --decode
   ```
3. Visit the web UI; authenticate through Authelia
4. Complete initial administrator setup with the token
6. Create a library pointing at `/books`

## Storage and secrets

- BookOrbit container
  - `/books` is `/seedboxmedia/Books/BookOrbit`
    - The directory itself is `chown`'d in an init container, but not recursively
  - `/data` contains app runtime state, including covers
    - Annotated for backup
- Postgres
  - `PGDATA=/var/lib/postgresql/data/pgdata`
    - Not annotated for backup directly
  - `/tmp` is disposable writable storage
- `bookorbit-env` secret
