# psyops: Personal SYs OPS

Shit I use to manage my own infrastructure

## Using PSYOPS

PSYOPS makes some assumptions, and we provide a wrapper script to manage them. Note that the script requires Python 3.6.

    # Show help
    ./psyops.py --help

    # Build the Docker image
    ./psyops.py build

    # Run the image
    ./psyops.py run

    # Build the image and run it immediately
    # Will not attempt to run the image if building fails, which is
    # particularly useful under Powershell, which doesn't have &&
    ./psyops.py buildrun

    # Perform repository (and submodule) operations
    # See more information in the section below about line endings
    ./psyops.py repo

The assumptions we try to make are:

- The current directory, a git repo, should be mounted to /psyops with permissions so the psyops user can read/write
- There is no permanent storage in the Docker container
- The Docker container is invoked with --rm
- Any persistent data should be in the /psyops volume, bind-mounted to the host

See the section below on submodules for more details on how they are used

## Line endings

It's critical that repositories with shell scripts have Unix line endings, but by defaut Git for Windows turns on the `core.autocrlf` setting, which checks out files using Windows line endings (while converting them back to Unix line endings upon commit). Without turning this off system-wide, you have to do something like this:

    # The parent repository
    git config core.autocrlf off
    rm .git/index
    git reset --hard HEAD

    # Each submodule:
    rm .git/modules/submod/dhd/index
    cd submod/dhd
    git reset --hard HEAD
    # ... repeat for all other submodules

This step is not necessary on Unix platforms

The `psyops.py` wrapper script can handle iterating through all submodules and the main repo and performing these actions. Note that the command will fail if there are uncommitted changes.

    psyops repo fixcrlf

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

See the section below on the secrets module for more information about how it is used.

## Submodules

We make heavy use of submodules, to avoid checking out code during build, which slows down the build and can incur rate limit errors. Understanding how Git interacts with submodules is important to understanding how PSYOPS works. In a bad case, an improper understanding of submodules can cause loss of data - for instance, if you don't realize that a change to a submodule has to be committed and pushed separately from changes to the parent module.

Submodules are available in the repository as well, as long as this repo is mounted to the /psyops volume. They can be used exactly the same way on the host or in the container, and you can edit files on the host while using them in the container - it's very useful to use a graphical editor on the host to modify files that are used on the command line in the container.

## Setting up the secrets submodule

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
