# Remoting

We'd like to support certain actions from the controller:

- Running arbitrary commands on many machines at once
    - Probably in a shell so you can use regular stuff like `cd` and `&&`
    - The inventory knows about SSH host keys and connection addresses, so use that
    - In the future the inventory knows about private network addresses, so make using those optional
- Build the Python package, upload it, and run it

Possibilities:

- Fabric
    - Interestingly it shares some concepts with us, like an inventory with hosts and roles
    - It currently requires TOFU for hosts, lol what <https://github.com/fabric/fabric/issues/1804>
- Paramiko
    - More flexible
    - No concept of groups or parallelism, have to build that ourselves
    - Can copy files and run shell commands
- Shelling out to ssh and scp
    - Stupid hack, we can write a known_hosts file to a temp location and tell ssh about it
    - No external libraries required
- Mitogen
    - Naturally threaded and async, with easy ability to depend on multiple async calls
      <https://mitogen.networkgenomics.com/getting_started.html#waiting-on-multiple-calls>
    - Can run locally-defined Python classes on remote systems
    - No dependencies other than Python and ssh
    - Does unfortunately require a temp known_hosts file as it just shells out to ssh, which also requires this
    - No direct file copy functionality, but I think you can just, read the file locally and write the file remotely, right?
    - I love mitogen
    - It does wayyy more than we need here
    - "ultimately it is not intended for direct use by consumer software", yes ha ha ha YES
    - Fun????????????
