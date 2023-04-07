# Writing progfiguration roles

* Every role needs an `apply()` function which performs the work.
  The `apply()` function should accept a `LocalhostLinuxPsyopsOs` argument (usually called `localhost`),
  and an `Inventory` argument (usually called `inventory`),
  and can define any other arguments after that.
* Roles may have a `defaults` dict that contains defaults for any arguments aside from `localhost` and `inventory`.
* Roles may have a `results()` function that takes the same arguments as `apply()`.
  Its purpose is to allow calculating role-specific values without re-running the role,
  and allowing other roles to use those values.
  While you can put any code you want in `results()`,
  the intention is that code is very fast to run.
  See below for more information.
* Roles then must be applied to functions in `inventory.yml`.

TODO: Create a ProgfigurationRole class to handle both `apply()` and `results()` arguments.
I could avoid repetition by defining the class in one place.
This would also mean we don't have to `hasattr(rolemodule, 'defaults')` etc.

## Example role module

Here's a role that creates a service account.
Other roles might want to know the homedir for the service account,
so that is returned in `results()`.

(In production, a role probably does more than just create a single user;
perhaps it creates this user as part of deploying a service.
We just use this tiny role as an example.)

```python
"""Set up a data disk"""

import os
import subprocess
from typing import Any, Dict, List

from progfiguration import logger
from progfiguration.localhost import LocalhostLinuxPsyopsOs

defaults = {
    "username": "svcuser",
    "groupname": "svcgroup",
}

def apply(
    localhost: LocalhostLinuxPsyopsOs,
    username: str,
    groupname: str,
):
    localhost.users.add_service_account(username, groupname, home=True, shell="/bin/sh")
    homedir = localhost.users.getent_user(username).homedir

def results(
    localhost: LocalhostLinuxPsyopsOs,
    username: str,
    groupname: str,
) -> Dict[str, Any]:

    homedir = localhost.users.getent_user(username).homedir
    return {
        "username": username,
        "groupname": groupname,
        "homedir": homedir,
    }

```

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
