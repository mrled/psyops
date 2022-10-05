# Design of progfiguration

I started with the premise, what would an Ansible look like if it was Python code instead of YAML documents?

Desired features:

- very fast installation
    - We get this from Alpine APK packages; unfortunately Python package installation is much worse.
- very fast execution
    - It's pretty good even though it's just Python. MUCH faster than Ansible.
- controller/nodes/groups/roles/functions
    - Controller is the machine that builds the package
    - Nodes are just hosts, like Ansible hosts
    - Groups are groups of hosts
    - Roles are Python submodules that configure hosts, like Ansible roles
    - Functions are groups of roles that are set for a specific host, kind of like playbooks except you just get one per host
- Good segmented encryption
    - The entire package, including all roles and info about other hosts, gets installed to every node
    - Need to be able to encrypt secrets for one host without other hosts being able to decrypt
    - Separate age key on each node, master age key on the controller
    - Add tooling to encrypt/decrypt secrets from the controller to make this easy.
- VERY SIMPLE. You don't get idempotency for free, but like, it's not that hard.
- A small library for useful things like file templates. This is mostly contained under the `localhost` module.
- Not require third party libraries installed on remote nodes (required for build / on the controller is ok)
- A good standard library in scope, a single point of trust, the opposite of NPM's problem

## Is Python the right language?

Features I'd like that Python doesn't offer:

- Single binary deployment, without an APK package, that can be executed from anywhere
- The ability to build dependencies into the single binary, so that we can use third party libraries, like a "statically compiled" binary
- Very fast builds. Python builds are like, okay, I guess. It could be a lot better.
- Nicer support for running shell commands.
    - Shell scripts are much better in this regard, and much worse in every other reguard.
    - Powershell is a great solution for this from a dev experience point of view, but much worse when it comes to speed
    - I'm not sure that Python is any worse than any language other than those two

Is it worth considering something else?

- Golang
    - Unergonomic error handling, which is kind of a big deal for shell scripts, and also for every other kind of program
- Rust
    - Unergonomic, lots of work for roles
    - Slow compile
- Java (or something on the JVM)
- C# (or something on the CLR)

Can we fix any of these with Python somehow?

- [stickytape](https://github.com/mwilliamson/stickytape) can assemble a Python module of multiple files into a single script (not necessarily human readable)
    - Looks interesting, but it can't include static data
- Apparently you can zip up Python modules and run them directly
    - [The zipapp module](https://docs.python.org/3/library/zipapp.html)
    - Apparently works with package data
    - We could vendor any dependencies and include them, but we'd have to do this manually and also handle updates when we care about them
    - Cannot load compiled extensions, so we can't use this for like, `requests` which uses `crypto` which uses C and Rust
    - Imports are a bit slower, which is a concern since each host is an import; not sure how much slower
- Can we make builds faster?
    - <https://zameermanji.com/blog/2021/6/14/building-wheels-with-pip-is-getting-slower/>
    - <https://pythonspeed.com/articles/faster-pip-installs/>
    - Making the zipfile is MUCH faster actually
- Can we improve the DX for shell commands?
    - Compare the current situation to `invoke`'s support... it's just `run("cmd with arguments asdf")`.
