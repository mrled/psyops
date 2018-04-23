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

- The current directory, a git repo, should be mounted to $PSYOPS_VOLUME with permissions so the psyops user can read/write
- There is no permanent storage in the Docker container
- The Docker container is invoked with --rm
- Any persistent data should be in $PSYOPS_VOLUME, bind-mounted to the host

See the section below on submodules for more details on how they are used

## Line endings

It's critical that repositories with shell scripts have Unix line endings, but by defaut Git for Windows turns on the `core.autocrlf` setting, which checks out files using Windows line endings (while converting them back to Unix line endings upon commit). You have a few options to deal with this:

1.  Turning it off system wide, like this:

        git config --global core.autocrlf false

2.  Cloning the repo, then in the main repo and each submodule, changing the setting and resetting the checkout directory:

        # The parent repository
        git config core.autocrlf off
        rm .git/index
        git reset --hard HEAD

        # Each submodule:
        rm .git/modules/submod/dhd/index
        cd submod/dhd
        git reset --hard HEAD
        # ... repeat for all other submodules

3.  Using the `psyops.py` script to automate the second step all at once:

        ./psyops.py repo fixcrlf

This task is not necessary on Unix platforms

## Recommended Docker settings

### Detach keys

Docker is dumb as hell, and has made `ctrl-p,ctrl-q` the default key sequence to use for detaching from an interactive container, even though bash has made `ctrl-p` the default key sequence for "previous command" (the same as the up arrow) since forever. There are two ways to change this; the following examples use `ctrl-i,ctrl-i` instead:

1. Pass `--run-args="--detach-keys 'ctrl-i,ctrl-i'"` when running the psyops image
2. Add a line like `"detachKeys": "ctrl-i,ctrl-i"` to `~/.docker/config.json`

The `~/.docker/config.json` file is documented [here](https://docs.docker.com/engine/reference/commandline/cli/#configuration-files).

## Creating a GPG key for use

We bake an encrypted GPG key into the image, and use a Python script called `psecrets` to decrypt it when the container starts. See the `psecrets` help (or just start the container and read the help text) to learn how that works. See below for how the key and other data was initially generated.

Our exported key and associated information was exported as follows. Note that this was done on a system with no existing keys (or indeed even a `$HOME/.gnupg` folder); if you export ownertrust on a system that has an existing key, you may get unexpected results.

    gpg --gen-key
    # ... and then answer the interactive questions to your liking ...
    # You almost certainly want a passphrase, since the key will be baked in

    gpg --list-secret-keys
    keyid="KEY ID FROM ABOVE"

    # Export the secret key
    # If it was encrypted with a passphrase in the first step, the export will
    # be encrypted as well.
    gpg --armor --export-secret-key $keyid > psyops.secret.gpg.key.asc

    # Export the (unencrypted) public key
    gpg --armor --export $keyid > psyops.secret.gpg.pubkey.asc

    # Export the (unencrypted) ownertrust database
    # If we import the secret and public key without importing the ownertrust
    # db, GPG will not trust our keys
    gpg --armor --export-ownertrust > psyops.secret.gpg.ownertrust.db.asc

See the section below on the secrets module for more information about how it is used.

## Submodules

We make heavy use of submodules, to avoid checking out code during build, which slows down the build and can incur rate limit errors. Understanding how Git interacts with submodules is important to understanding how PSYOPS works. In a bad case, an improper understanding of submodules can cause loss of data - for instance, if you don't realize that a change to a submodule has to be committed and pushed separately from changes to the parent module.

Submodules should be available inside the container as well, as long as this repo is mounted to the `$PSYOPS_VOLUME` volume. They can be used exactly the same way on the host or in the container, and you can edit files on the host while using them in the container - it's very useful to use a graphical editor on the host to modify files that are used on the command line in the container.

That said, see above for notes about line endings if your docker host is running Windows.

## Setting up the secrets tarfile

We use an encrypted tarfile to manage secrets.

To create the encrypted secrets file:

1.  Start the PSYOPS container
2.  Place your secrets in `$PSYOPS_SECRETS_PATH`
3.  Add your symlink script (named the same as the value of `$PSYOPS_SECRETS_POST_DECRYPT_SCRIPT_PATH`)
4.  Call `psecrets encrypt`
5.  The encrypted secrets file is now saved to `$PSYOPS_SECRETS_ENCRYPTED_PATH`
6.  Make sure to commit that file to the PSYOPS repository


## Build and run -time variables

If at all possible, we define variables like usernames, special paths, and so forth in only one place, so that changing them later is not a hassle.

The Dockerfile has some constructs that help us with this:

* ENV statements are shell environment variables that are *settable* while *running* the container and *readable* while *building or running* the container.
* ARG statements are shell environment variables that are *settable and readable* only while *builing* the container

Some ENV statements are used during build, and the container will not work properly if their values are changed at runtime; see the Dockerfile and note any variables that are used during that time.

There is one kind of magic string that must be set in more than one place: variables that our wrapper script passes to `docker run`. These must be set to the same values in both `Dockerfile` and the `psyops.py` wrapper script. At the time of this writing, this includes only:

- The psyops volume path (`ENV PSYOPS_VOLUME="/psyops"` in the Dockerfile)
- The secrets tmpfs mount point (`ENV PSYOPS_SECRETS_PATH="/secrets"` in the Dockerfile)
