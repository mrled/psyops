# Why progfiguration?

* A node should be able to configure itself at boot without calling out to a controller
* Speed
* Power

## Nodes configuring themselves without a controller

I have been familiar with the model where a node boots,
and immediately reaches out over the network and asks a controller to configure it.
This makes secrets management particularly easy --
the controller knows all the secrets,
and if one of them applies to a node's config,
that node will be given a decrypted version of it.

The downside is that it requires a controller to be always online
and with a decrypted secrets store.

I have an interest in asynchronous endpoint-to-endpoint management,
because this sidesteps a vulnerable chokepoint for malicious actors and regulatory bodies
(which are indistinguishable),
and means you never have to have the full secret store sitting decrypted
on someone else's hardware or in someone else's datacenter.
It can instead live on your laptop.
(I don't claim this is foolproof, or that it's best for everything,
just that it's something I'm interested in.)

To accomplish this, we encrypt all secrets with age,
and distribute all of them to all nodes in a single unified package.
The package can live on an Internet host that cannot decrypt the secrets, like S3.

It's really a type of end-to-end encryption, if you think about it --
one end is the administrator's workstation, and the other is the node being managed.
No controller in between that has to provide uptime.

Some side effects of this that might be interesting:

* Storing the last-downloaded configuration in case the network is not accessible at next boot
* Fully offline machines, or airgapped machines

## Speed

Ansible does a lot of things, and those things cost time.

Progfiguration doesn't do nearly as much, which takes less time.

Ansible's features can be very useful, and sometimes it's hard to do without them.
But wow the speed is nice, especially for small inventories.

## Power

Progfiguration is designed around the principle of _just let me write code, dammit_.
In Ansible, you can do anything:
[filters are pure functions, and actions are functions with side effects](https://me.micahrl.com/blog/ansible-filter-pure-function/).
But you can't just do anything in the normal course of writing a playbook (or a role).
In Ansible, you have to think in two modes:
you can use the extensive and powerful existing actions
that are part of the standard package or community extensions,
or you can write your own.
Doing the latter requires changing modes from writing YAML documents to writing Python programs,
and in addition to Python, you have to understand how Ansible does things.

(You can also deploy a script and run it, or do some limited oneliners with the `cmd` module.
As someone who has done both, this is awkward at best.)

In Progfiguration, it's all Python.
You still do have to know something about progfiguration itself,
by following the [Roles API](./roles.md).
However, when writing roles, you're just writing Python.
Progfiguration ships with a small number of convenience functions like the `localhost` module,
but they are also just Python, and you can do without them if you want.

An aside: the standard library is trying to hit the 80/20 principle,
not be a complete interface.
For instance, we have functions like `lines_in_file()`,
but they won't work for every possible use case.
Users are encouraged to take the convenience code functions and adapt them to their needs.

To be honest, Ansible might have this distinction right.
I know that I've had colleagues who could easily ramp on Ansible
who would have had a much harder time contributing to a pure Python configuration package like progfiguration.

That said... if you _do_ already know a real programming language,
how fucking frustrating is it to be forced to interact with it through YAML?
Progfiguration is, if not a bet against,
an exploration in the other direction of the YAML interface.

## Lesser differences

### Variables are scoped

Ansible's global variables are a blessing and a curse.

For my personal projets, I always prefix the role name for each variable,
so a role `nginx` with a variable containing the hostname contains `nginx_hostname`.
This can get really unwieldy!
Also my coworkers don't follow it consistently no matter how much I beg.

On the other hand, in **any** file inside **any** role you can reference a variable defined in **any** location.
This is powerful, but if you don't name your variables carefully,
you end up having to grep for `hostname` in a repo with dozens of roles and thousands of files.
(You cannot restrict your grep to just YAML files,
because it could be referenced in a template;
you cannot restrict your grep to just `\{\{ ?hostname`,
because it could be used in an expression like `when` that doesn't require it, or used in a filter, etc etc.)

(This is one area where Ansible's easy ramp for new contributors can also be a downside.
Left unchecked, poorly named variables can cause persistent problems,
and new contributors have no experience to guide them in how to name variables thoughtfully.)

On the other hand, in progfiguration, variables are scoped.
Role variables must be passed in directly from groups or nodes;
template variables must be passed in explicitly to `localhost.temple(...)`.
This adds some verbosity, but that's negligible compared to my preferred method of
prefixing each variable name with the role it is referenced in.

Since the whole thing is just Python anyway,
you can define site global variables for things that are really inconvenient to pass around.
Also since this is Python,
there are convenient editor functions for finding and/or renaming symbols _globally_,
across your entire project.
VS Code is what I'm familar with,
and with it at least you can rename a variable referenced in other files automatically.

#### Aside: How could Ansible improve this?

* Much better editor support for global find/replace of variables.
  Ansible itself ultimately knows where all the variables go;
  your editor should too.
* Much better editor support for understanding a role's inputs.
  The user has to read and understand the entire role, including all templates,
  in order to know all of its inputs.
  The editor should do this automatically and somehow present this to the user.
  (It probably also ought to fail to partially run the role if all mandatory inputs are not set.)

### Simplified directory structure

If I may quote [myself](https://twitter.com/mrled/status/1537172285655764999):

> Building Ansible extensions in Python is awesome because it means your editor has 12 tabs open named `main.yml` and 6 more open named `__init__.py`

Progfiguration solves half of this.
You are still stuck with a bunch of files open named `__init__.py`,
but the YAML stuff is gone.

Also, though this is neither the time nor place,
as someone who will likely have to write Ansible in the future,
a plea: can Ansible simplify its directory structure a bit?
Do we really need support for multiple vars/defaults/meta files by default?
Do we have to differentiate between files we're copying directly and files that we might template?
Must we create a directory for each type of thing?
I propose:

```text
roles/
  rolename/
    tasks.yml
    tasks/
      ... an optional folder with extra tasks files if you need
      some_other_stuff_to_do.yml
    vars.yml
    defaults.yml
    meta.yml
    files/
      untemplated_script.sh
      templated_config_file.conf.j2
```
