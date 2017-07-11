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

    gpg --gen-key
    # ... and then answer the interactive questions to your liking ...

    gpg --list-secret-keys
    keyid="KEY ID FROM ABOVE"

    gpg --armor --export-ownertrust > psyops.secret.gpg.ownertrust.db.asc
    gpg --armor --export-secret-key $keyid > psyops.secret.gpg.key.asc
    gpg --armor --export $keyid > psyops.secret.gpg.pubkey.asc

## Setting up the Git repository

We use [git-remote-gcrypt](https://spwhitton.name/tech/code/git-remote-gcrypt/) to handle secrets. The repository was set up like this:

Note the URL fragment when adding the `gcrypt` remote - the fragment represents the branch name that `git-remote-gcrypt` will push to. When it pushes, it flattens git changes into one commit (changeset) per file, and then on checkout it reconstitutes that into a repository that `git` can work with locally with full history. This means that the `master` branch is encrypted that way too... but since we don't push to that branch with `git-remote-gcrypt`, and instead use the `encrypted` branch, `master` can stay decrypted for our readme.

    # Assumes an existing GPG key
    git init psyops-secrets
    cd psyops-secrets
    echo 'Secrets for [PSYOPS](https://github.com/mrled/psyops)' > readme.markdown
    git add readme.markdown
    git commit -m "Add readme"
    git remote add encrypted git@github.com:mrled/psyops-secrets.git
    git push -u encrypted master:master -f

    # The URL fragment, '#encrypted', means to push to a remote branch called 'encrypted'
    # This leaves our master branch alone, in case we want to add non-secrets there
    # However, note that the master branch is still encrypted and pushed to the 'encrypted' branch too
    git remote add gcrypt 'gcrypt::git@github.com:mrled/psyops-secrets.git#encrypted'
    git config gcrypt.gpg-args "--batch --no-tty --passphrase-file $HOME/.gpg.passphrase"
    git checkout -b decrypted encrypted/master
    git push -u gcrypt decrypted:encrypted
