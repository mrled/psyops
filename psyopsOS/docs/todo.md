# Todo

* Document the `telekinesis` / `tk` package.

## Ideas

* A/B updates
    * Recent progress on this front: building grubusb images
    * Break the `tk mkimage grubusb` stage `diskimg` into several stages: assembling files including memtest into a directory, and actually building a disk image. We might need to ship a single recent raw image to deaddrop (??), but mostly we'll be shipping the individual files so that booted systems can write them to the ext4 A/B partitions.
    * Make a `tk` command to deploy built kernel/squashfs/initrd/DTBs/etc to deaddrop. Use a date based version system, and write a file that contains the latest deployed date.
    * Convert `make-grubusb-img.sh` to a Python script that can both create an image from scratch with A/B/secret/EFISYS partitions, and also one that can update these partitions independent of one another. Normal case will be to update the A/B partition (whatever hasn't been booted from), but we may want to update the grub configuration, memtest, etc as well. This script will have to run on both remote nodes for updating individual partitions, and on builder machine to generate new disk images.
        * Script on each node must:
            * Check deaddrop for new version (maybe this is a different script/service)
            * Mount the non-booted A/B partition, write each file to it, and remove any files that should no longer be used (maybe this happens with DTB files?)
            * Secondarily, should be able to update PSYOPSOSEFI partition and GRUB configuration, and memtest or any other things we boot that way
        * Script on the builder must:
            * Find artifacts from previous build steps: kernel/initrd/squashfs/memtest/DTBs/etc
            * Zero out the existing image
            * Write the PSYOPSEFI partition from scratch
            * Write the secrets partition if requested, or an empty partition for a generic image
            * Write the A and B partitions
    * Write an update script that checks deaddrop and applies updates to the non-booted A/B partition. Could also warn about out of date grub config or memtest.
    * Update format
        * Originally this was going to be separate files: `kernel`, `initramfs`, `squashfs`, `boot/**` for DTBs, `System.map`, `config`.
        * I could manage a version with a `manifest.json` that includes each file...
        * But eventually it seems simpler to just make a tarball and go from there. A tarball makes the DTB situation easier, and can be extracted while downloading.
* A role to control psyopsOS secrets from progfiguration
    * Secrets still have to be mounted by the psyopsOS postboot startup script
    * progfiguration can check whether each file matches what it has internally
    * If any of them do not match, remount the volume rw and copy that file, then remount again ro
* Further enhancement: allow easier creation of the secrets partition
    * Write psyopsOS-base script to create the partition
    * Copy just progfiguration itself to a brand new node
    * progfiguration then has to contain ssh host keys etc
    * Run script with path to progfiguration, age secret key, and node name as arguments, and it does everything
* Add a `pause_syslog_logging` context manager so that I can do things like restart syslog without errors
    * Currently progfiguration sends logs to syslog if it can write to `/dev/log`
    * If I restart syslog or replace busybox syslog with syslog-ng, this prints lots of errors
    * Add a context manager so I can do those actions with `with pause_syslog_logging: ...`
      and avoid generating the errors
    * Maybe with an argument like `with pause_syslog_logging(logfile="/var/log/syslog.paused"): ...`
      so that it can write log lines there for troubleshooting.
    * Alternative: don't log to syslog by default, just log to a file in /var/log directly and avoid this
* Research using Mozilla SOPS instead of my own custom thing
* Make an update mechanism
    * Service that checks for OS updates once/day or something, maybe via similar method like `psyops.micahrl.com/os-update.json`
    * If there's an update, download it to a temp dir, and overwrite the USB drive that contains the OS with it. I hope u tested it!
* Tor roles
    * A Tor for all networking mode. Could implement as a role in progfiguration, but better to do as a different flavor of ISO, so that it is up before anything uses the network at all.
    * Offline identity keys <https://support.torproject.org/relay-operators/offline-ed25519/>
      w/ master key on controller which deploys signed keys periodically to nodes.
* Surface system health quickly
    * Bash prompt shows whether initial boot completed successfully?
    * Bash prompt shows whether latest run of progfiguration completed successfully?
    * An HTTP endpoint shows system health?
* Misc
    * Use `AuthorizedKeysCommand` as described [in this GH issue](https://github.com/coreos/afterburn/issues/157) to support an `authorized_keys.d` directory (maybe named so as not to conflict with a possible future support of this, like `psyopsos_authorized_keys.d`.) This would make psyopsOS-base's installation of root SSH keys easier and less error prone.
    * Run a daemon to share non-secret info like ISO generation time, installed version of important packages, postboot log.
* Alert when psynet is not accessible, handle lighthouse auto updates, etc
    * Recent problem where I had to run the python script to setcap the binary on the lighthouses again... not sure why
    * Make some kind of alert system for when hosts on psynet can't talk to each other. Took me a LONG time to see that the whole thing wasn't working properly.
    * Should also be auto-updating lighthouse nebula binaries
    * Should also auto-update the OS on lighthouses
    * Can I move lighthouse deployments to psyopsOS? Maybe not worth it if I can get auto updating handled.
    * Would be nice to move them to progfiguration though.
    * Update psynet Route53 zone from progfiguration.
    * Send lighthouse syslog to syslog collector
* Run tasks from the progfiguration controller
    * Example: Updating psynet Route53 zone
    * Example: Connect to remote host and configure it. Useful for appliances where I might not want to run a full Python package, especially if they have an older version of Python.
    * On the other hand, could just handle these tasks with Invoke and tasks.py? Simpler solution that requires less custom code in progfiguration.
* Handle multiple remote deployments more asynchronously
    * Push the package to the package store (eg psyopsOS APK, a pip server, whatever)
    * SSH to each remote host and tell it to pull the package and apply it itself and write the logs to a dedicated location I can find.
    * Poll the log file location over SSH and report back.
* Secure DNS for psynet
    * Lighthouses can offer a DNS service. It's experimental, and it doesn't support querying upstream servers.
    * Would be nice if we could rely on DNS without having to trust lighthouse infrastructure.
    * Right now we have public DNS entries for private addresses, but this doesn't work with reverse DNS.
    * Could keep single source of truth for psynet that generates hosts files (for reverse DNS) and sets entries in Route53 (for clients like macbook, iphone, etc). However, this causes a distribution problem at scale.
    * Would like to avoid requirement for constant DNS service uptime as it is very disruptive if it goes down and I don't have multiregion physical datacenters and I would like to avoid trusting the cloud.
    * Would be cool if we could somehow look up current owner of an IP address per the nebula CA on some local daemon. Distributed. There is a single source of truth for entire DNS space - the nebula CA - so this doesn't violate CAP. However, I'm not sure the information is there.
    * One place that reliable reverse DNS would be nice: syslog-ng use_dns. syslog-ng blocks on DNS lookups, and warns you that this can be used to create DOS attack. Right now only reliable way to do this is with a hosts file... you can tell syslog-ng to only look in hosts file, but then that requires an up to date hosts file.
    * I guess we can punt on the general case for rdns and scalability, and in the specific case of DNS, have a single source of truth for DNS mappings, which generates nebula certs + Route53 entries + a hosts file for syslog server.
* Make a way to add a node with a single command. Generate keys it needs, re-encrypt groups its in, create a filesystem for a usb drive, add them to the progfigsite checkout. Avoid Docker?
  * Implemented an early version of this in `progfigsite_node_cmd.py`, but doesn't create the filesystem or re-encrypt groups
  * Move `progfigsite_node_cmd.py` functionality into `tk`. This will fix some code dupe and makes more sense ultimately as that command creates a new psyopsOS node.
  * Write out a known_hosts file when creating a new node - Can configure ssh clients to use multiple `known_hosts` files
* IDEA: single command build/copy/update/reboot
  * Use case: Run a command and walk away during build
  * No CI; use local machine as CI
  * Pull all secrets out of password manager at the beginning. That way you can let password manager lock, no worries with long builds etc
  * Expect a command on remote systems to tell us what the boot disk is
  * Expect a command on remote system to tell us whether to use tmp space somewhere for boot disk, or dd it directly to the drive (risky)
  * Run pipe that will dd iso image from local machine to the remote host. If either of the above commands fail, don't write anything.
* Idea: bit torrent iso distribution
  * machines can dedicate disk space to seeding, or not
  * local machine always seeds
  * build versioned iso files
  * no CI again, this avoids that requirement if local dev is set up
* Add better caching to `tk` for builds. Meaning, it works like `make`, where it'll regenerate an artifact only if its dependencies have changed. Probably have to do this myself?
* Make psyopsOS startup faster - the `local` service hangs until `progfiguration` finishes, which is not ideal
* An SSH CA
