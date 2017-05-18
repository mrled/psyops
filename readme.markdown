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
