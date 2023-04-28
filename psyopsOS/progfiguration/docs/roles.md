# Writing progfiguration roles

* Rules must be a subclass of `ProgfigurationRole`, annotated with `@dataclass(kw_only=True)`
* They may provide extra fields
* They should have an `apply()` method that does the work of the function.
* Roles may have a `results()` function that returns role-specific values without re-running the role,
  and allowing other roles to use those values.
  While you can put any code you want in `results()`,
  the intention is that code is very fast to run.
  See below for more information.
  Code in `results()` should NOT expect that `apply()` has already run.
* Roles then must be applied to functions in `inventory.yml`.

## Example role module

Here's a role that creates a service account.
Other roles might want to know the homedir for the service account,
so that is returned in `results()`.

(In production, a role probably does more than just create a single user;
perhaps it creates this user as part of deploying a service.
We just use this tiny role as an example.)

```python
from dataclasses import dataclass

from progfiguration import logger


# This annotation is mandatory - without it you will get errors about class arguments
@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    # These are arguments that you can pass to your role
    # Arguments that have no default value are required
    username: str
    groupname: str
    # Arguments with a default value are not required, but can be overridden
    shell: str = "/bin/sh"
    # Note that lists/dicts require default_factory
    secondary_groups: field(default_factory=list)
    # You can also use a lambda to pass an arbitrary default_factory value
    touch_files: field(default_factory=lambda: ["/tmp/one", "/etc/two", "/home/three"])

    # It can be nice to set a proeprty as a way to define values in one place
    @property
    def homedir(self):
        return return Path(f"/home/{self.username}")

    def apply(self):
        self.localhost.users.add_service_account(self.username, self.groupname, home=self.homedir, shell=self.shell)
        for g in self.secondary_groups:
            self.localhost.users.add_user_to_group(self.username, g)

    def results(self):
        return {
            "username": self.username,
            "groupname": self.groupname,
            "groups": [self.groupname] + self.secondary_groups,
            "homedir": self.homedir,
            "shell": self.shell,
        }
```

Nodes or groups may override default values, or they may choose to accept them.
If a default is not provided by the role,
it must be applied by any node that applies the role,
or (at least) one of the groups that that node is a member of.

Group order is not guaranteed.
Make sure you do not allow multiple groups for the same node to define the same argument.

## Some notes on the `results()` function

This function should return _easy to calculate_ values.
This is a judgement call, but note that other roles may reference the results multiple times.

In the design of this API, I considered allowing `apply()` to return results directly,
and possibly caching them for later use.
The complexity of that design caused me to reject it, at least for now.
Instead, the `results()` design has some tradeoffs,
like needing to factor out code that is shared by `apply()` and `results()`,
and no ability to cache.
However, in exchange, the implementation is simpler.

TODO: is there a better name for this function than `results()`?
The `results()` name implies that `apply()` calculates values and caches them,
but that's not what we're doing.

## Deprecated: `appends` arguments

We used to have the concept of `appends` arguments, which could be appended to but not overridden.
They used a `.appends` property on the role.
They added complexity for little value, however.

I realized that I only ever used them for things defined as default role argument values anyway.
I could handle this more cleanly by just appending those inside the role itself and documenting it.

## Notes on role references

Role references, and therefore `results()` values, must be
_completely computable before the role has run_.

This means that you should **avoid** doing something like this:

```python
@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    username: str

    # Homedir is calculated based on state of the system --
    # this will fail before the user is created.
    @property
    def homedir(self):
        return self.localhost.users.getent_user(self.username).homedir

    def apply(self):
        self.localhost.users.add_service_account(self.username, self.username, home=True)

    def results(self):
        return {
            # Homedir is returned in results():
            "homedir": self.homedir,
        }
```

To fix this, you can either:

1. Define the homedir as a static path and pass it as an argument to `add_service_account()`
2. Decide not to return the homedir in `results()`

Here's an example of the first option:

```python
@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    username: str

    # It is safe to refer to self.username, which is passed in when the Role class is instantiated
    @property
    def homedir(self):
        return Path(f"/home/{self.username}")

    def apply(self):
        # Rather than `home=True`, which creates the homedir in the default location,
        # we pass the homedir location directly.
        self.localhost.users.add_service_account(self.username, self.username, home=self.homedir)

    def results(self):
        return {
            # The homedir is defined statically so it can be returned in results()
            "homedir": self.homedir,
        }
```
