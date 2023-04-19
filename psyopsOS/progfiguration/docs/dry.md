# Don't Repeat Yourself

I don't like repeating myself to computers.

How can we avoid this in progfiguration?

* `RoleResultReference` objects could use the value from `result()` on a `ProgfigurationRole`
  This is still explicit - a role that needs an output from another role still accepts a parameter for it, unlike a globals scheme.
* What about calculations from results though?
  Right now I have datadisk_v2, which is a psyopsOS role that adds a data partition (`/psyopsos-data` by default).
  I want to have a path for storing role-specific data (`/psyopsos-data/roles/<rolename>` by default).
  I can have return a result of `/psyopsos-data/roles`, but I'll still have to add the rolename for every role that needs it.
  They'll also all have to mkdir it.
  This is boilerplate.
* I could have some kind of global value, maybe in the `site` package there is a `globals.py` that defines stuff like this.
  One thing I don't like about this is that it's a step closer to Ansible variable soup,
  where you have variables injected all over the place and no idea where they came from.
  I guess we're not _that_ close to this, though... if you are explicitly calling `lookup_global("varname")`
  then it actually is clear where it comes from.
  Still, it means that a role's `apply()` signature is not the complete interface for what is required to run the role.
  I guess one way around that is to reference the globals in group/node definitions -
  then we can still define it once and pass it to any role, but we don't have soup.
* On the other hand, I could just hard-code `/psyopsos-data/roles` everywhere and rely on ripgrep if I need to change it.
  Is that more in the spirit of what I'm doing here? It errs on the side of simplicity.
* Part of the question is how many layers of abstraction do I want to maintain?
  * Simple: abstractions in progfiguration like roles/nodes/groups, abstractions in the site like specific roles
  * More complex: my `/psyopsos-data` mountpoint only applies to psyopsOS nodes.
    Do I want roles to be specific to this? Maybe not. Maybe some roles will be used both in psyopsOS and in other operating systems.
    In that case, keeping everything as an argument passed to the role's `apply()` is nicer.
    However, it may create more boilerplate.

## An experiment: defining a `settings` role

* `results()` on each `ProgfigurationRole`
* A `settings` role with an empty `apply()` function, that just returns values in `results()`
* I could set values in `universal` group, which are passed to the `settings` role, and which that role's `results()` could perform calculations on.
  For instance, in the `universal` group:

        settings={
            "data_mountpoint": RoleResultReference("datadisk_v2", "mountpoint"),
            "role_storage_subpath": "roles",
        },

  and in the `settings` role:

        def results(
            self,
            data_mountpoint: Path,
            role_storage_subpath: str,
        ):
            role_storage_root = role_storage_root / role_storage_subpath
            role_storage = RoleStorage(role_storage_root)
            return {
                "data_mountpoint": data_mountpoint,
                "role_storage": role_storage,
            }

  and then other roles could use eg:

        capthook={
            "role_storage": RoleResultReference("settings", "role_storage"),
        },

* However, this still requires boilerplate.
  Inside the capthook role, I have to do something like:

        mydir = role_storage / "capthook"
        mydir.mkdir()

* Is all this complicated stuff really worth it?

The settings role I experimented with, in entirety:

```python
"""Set up a data disk"""

from dataclasses import dataclass
from pathlib import Path

from progfiguration.inventory.roles import ProgfigurationRole


@dataclass
class RoleStorage:
    root: Path

    def role(self, role: str) -> Path:
        return self.root / role


class Role(ProgfigurationRole):

    defaults = {}
    appends = []

    def apply(
        self,
        data_mountpoint: Path,
        role_storage_subpath: str,
    ):
        pass

    def results(
        self,
        data_mountpoint: Path,
        role_storage_subpath: str,
    ):
        role_storage_root = role_storage_root / role_storage_subpath
        role_storage = RoleStorage(role_storage_root)
        return {
            "data_mountpoint": data_mountpoint,
            "role_storage": role_storage,
        }
```

## Simplest solution: some repetition

* Pass in `/psyopsos-data/roles/<rolename>` to every role that needs it
* It has to match the mountpoint path in `datadisk_v2`
