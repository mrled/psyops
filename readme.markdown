# psyops: Personal SYs OPS

Shit I use to manage my own infrastructure

## Line endings

It's critical that repositories with shell scripts have Unix line endings, but by defaut Git for Windows turns on the `core.autocrlf` setting, which checks out files using Windows line endings (while converting them back to Unix line endings upon commit). Without turning this off system-wide, you have to do something like this:

    git config core.autocrlf off
    rm .git/index
    git reset --hard HEAD

    # Then you have to do this once for each submodule:
    rm .git/modules/dhd/index
    cd dhd
    git reset --hard HEAD

This step is not necessary on Unix platforms

## Creating a GPG key for use

We bake in a GPG key.

Our exported key and associated information was exported as follows. Note that this was done on a system with no existing keys (or `$HOME/.gnupg` folder).

    gpg2 --full-gen-key
    # ... and then answer the interactive questions to your liking ...

    gpg2 --list-secret-keys
    keyid="KEY ID FROM ABOVE"

    gpg2 --armor --export-ownertrust > psyops.secret.gpg.ownertrust.db.asc
    gpg2 --armor --export-secret-key $keyid > psyops.secret.gpg.key
