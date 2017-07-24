# psyops: Personal SYs OPS

Shit I use to manage my own infrastructure

## Line endings

It's critical that repositories with shell scripts have Unix line endings, but by defaut Git for Windows turns on the `core.autocrlf` setting, which checks out files using Windows line endings (while converting them back to Unix line endings upon commit). Without turning this off system-wide, you have to do something like this:

    git config core.autocrlf off
    rm .git/index
    git reset --hard HEAD

    # Then you have to do this once for each submodule:
    rm .git/modules/submod/dhd/index
    cd submod/dhd
    git reset --hard HEAD
    # ... repeat for all other submodules

This step is not necessary on Unix platforms

## Creating a GPG key for use

We bake in a GPG key.

Our exported key and associated information was exported as follows. Note that this was done on a system with no existing keys (or indeed even a `$HOME/.gnupg` folder); if you export ownertrust on a system that has an existing key, you may get unexpected results.

    gpg --gen-key
    # ... and then answer the interactive questions to your liking ...

    gpg --list-secret-keys
    keyid="KEY ID FROM ABOVE"

    gpg --armor --export-ownertrust > psyops.secret.gpg.ownertrust.db.asc
    gpg --armor --export-secret-key $keyid > psyops.secret.gpg.key.asc
    gpg --armor --export $keyid > psyops.secret.gpg.pubkey.asc

## Setting up the Git repository

We use [git-remote-gcrypt](https://spwhitton.name/tech/code/git-remote-gcrypt/) to handle secrets, which are stored in [psyops-secrets](https://github.com/mrled/psyops-secrets). This is how that repository was created:

1. Create the repo on GitHub

2. Push an initial commit containing data that is OK to be pushed unencrypted

        git init psyops-secrets-staging
        pushd psyops-secrets-staging
        echo 'Secrets for [PSYOPS](https://github.com/mrled/psyops)' > readme.markdown
        git add readme.markdown
        git commit -m "Initial commit - add readme"
        git remote add origin git@github.com:mrled/psyops-secrets.git
        git push -u origin master:master
        popd

3. Clone into a second location and configure `git-remote-gcrypt`

        git clone gcrypt::git@github.com:mrled/psyops-secrets.git psyops-secrets
        pushd psyops-secrets
        git config gcrypt.gpg-args "--batch --no-tty --passphrase-file $gpgpassfile"

    Note that when you clone it, it will say "You appear to have cloned an empty repository". This is because when using `git-remote-gcrypt` with a git SSH remote (which does not have permission to modify the .git directory directly) rather than an SFTP or rsync remote (which does), it must use a local intermediary repository. That local intermediary repository contains only encrypted data and not the existing commit, where the readme was added. (It then force-pushes to the remote repository a single commit, containing one file per changeset of your actual changes.)

    A benefit of this is that our readme works in GitHub while files, and even log messages and file names, are encrypted. However, history will not be available to GitHub, as the layout of the repository and even commit messages are all squashed into encrypted changeset files.

4. Add files and commit

        git add state-secrets.txt
        git commit -m "Adding important state secrets lol"
        git push
        popd

    Note that, in this case, we are using a file containing the passphrase. Use a literal string, not a shell variable for this, and of course it must exist and be the correct passphrase. There may be other options, such as using a GPG agent, that you might wish to explore instead.
