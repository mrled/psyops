# psyops submodules

Note that all submodules here must be public repositories,
and use `http://` URIs,
so that Netlify can fetch them.

To change a submodule URI locally to SSH for committing,
without changing it for all future clones of the repo,
use commands like this:

```sh
update_submod_uri_local_only() {
    reponame="$1"
    remotename="$2"
    localpath="submod/$reponame"
    sshuri="git@github.com:mrled/$reponame.git"
    git config "submodule.$localpath.url" "$sshuri"
    pushd "$localpath"
    git remote set-url "$remotename" "$sshuri"
}

update_submod_uri_local_only "dhd" "origin"
update_submod_uri_local_only "fourgang" "origin"
update_submod_uri_local_only "matrix-docker-ansible-deploy" "mrled"

git submodule update --recursive --remote
```
