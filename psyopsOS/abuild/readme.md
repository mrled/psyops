# psyopsOS abuild

Abuild names the repo after the parent directory of the package root.
Apparently I can't change this.
This is set in the abuild script as `repo=`.
<https://gitlab.alpinelinux.org/alpine/abuild/-/blob/f150027100d2488b318af935979c9b32ff420c71/abuild.in#L1022>
It corresponds to "main", "community", "testing" in the Alpine repository.

So, the `psyopsOS` subdirectory here will be our repo root.
Inside there will be package names.
E.g. `./psyopsOS/psyopsOS-base`.

Just like the official abuild repo,
some packages are self-contained, like `psyopsOS-base`,
while others rely on source code from elsewhere --
perhaps elsewhere on the Internet or elsewhere in the psyops git repository.
E.g. `neuralupgrade` is a Python package in `psyopsOS/neuralupgrade/`,
and it has a directory in our abuild repo at `psyopsOS/abuild/psyopsOS/neuralupgrade`.

## Previous versions

In the past, we've tried to hack around abuild's behavior of
naming the repo after the package's parent directory
by building packages in temp dirs.
This worked but it was kind of finnicky and clearly fighting the tooling.

The `progfiguration_blacksite` still does it that way.
