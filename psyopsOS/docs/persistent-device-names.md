# Persistent device names

Oh god.

## The problem

I want to provide persistent device names across reboots.
I'm not sure if this is relevant, but just in case:
I cannot rely on saving some information to disk somewhere, because the OS is stateless.

Unfortunately the disk that is seen as e.g. /dev/sda can change from reboot to reboot.
For instance, you could insert a disk ahead of it.

I was thinking we could use PCI paths to differentiate, but apparently this is not reliable!
(See the `~cks` reference below.)

Is it more reliable than bare `/dev/sda` like names?

Is there a better alternative?

## Programatically finding devices by PCI path in sysfs

I spent a lot of time on this; see commit `527ba9a5dae7047dfe5b2704533425779e2de1f1`.

The result worked - I could find a disk's sysfs path by looking in eg `/sys/class/block/sda`,
which would point to eg `/sys/devices/pci0000:00/0000:00:17.0/ata1/host0/target0:0:0/0:0:0:0/block/sda/`.
I could find a `/dev` path from a sysfs path by looking in the `dev` file in that directory
(so eg `devices/pci0000:00/0000:00:17.0/ata1/host0/target0:0:0/0:0:0:0/block/sda/dev`),
which would contain major:minor pair eg `8:0`,
and then look at eg `/dev/block/8:0` to see that it is a symlink pointing to eg `/dev/sda`.

It looked like all of those behaviors were stable behaviors default in recent kernels,
but it's possible that part of that shouldn't be relied on.

However, the worse problem was that I couldn't use these directly as device names.
Ceph needs to be able to do this, so I'm stuck.

## Can we make this work in mdev?

Alpine's default devd is mdev.

See `/etc/mdev.conf` to find that `/lib/mdev/persistent-storage` appears to be responsible
for creating `/dev/disk/by-id` and `/dev/disk/by-path`.

[persistent-storage](https://gitlab.alpinelinux.org/alpine/mdev-conf/-/blob/master/persistent-storage)
in git.

Find [this PR](https://gitlab.alpinelinux.org/alpine/aports/-/merge_requests/32330)
(see also "2022/2023 Alpine Linux changes to mdev, eudev" section below),
which adds the functionality.

I think we could extend this to work for `by-path`, by using information in `/sys`.

However, how safe is it to modify this script?
It doesn't look like it's designed for any end-user extensibility.

## OK, what about udev?

This appeared to work, until I realized it only had USB disks, not my SATA or NVME disks.

```text
kenasus:~# lsblk
NAME                                 MAJ:MIN RM   SIZE RO TYPE  MOUNTPOINTS
loop0                                  7:0    0 106.2M  1 loop  /.modloop
sda                                    8:0    0 238.5G  0 disk
sdb                                    8:16   1   3.7G  0 disk  /mnt/psyops-secret/mount
sdc                                    8:32   1   7.5G  0 disk
├─sdc1                                 8:33   1   696M  0 part  /media/sdc1
└─sdc2                                 8:34   1   1.4M  0 part
nvme0n1                              259:0    0 931.5G  0 disk
├─nvme0n1p1                          259:1    0   256G  0 part
│ └─nvme0n1p1_crypt                  253:0    0   256G  0 crypt
│   └─psyopsos_datadiskvg-datadisklv 253:1    0   256G  0 lvm   /etc/rancher
│                                                               /var/lib/containerd
│                                                               /var/lib/rancher/k3s
│                                                               /psyopsos-data
└─nvme0n1p2                          259:2    0 675.5G  0 part
kenasus:~# ls -alF /dev/disk/by-path
total 0
drwxr-xr-x 2 root root 120 Mar 20 21:40 ./
drwxrwxrwx 8 root root 160 Mar 20 21:40 ../
lrwxrwxrwx 1 root root   9 Mar 20 22:58 pci-0000:00:14.0-usb-0:3:1.0-scsi-0:0:0:0 -> ../../sdb
lrwxrwxrwx 1 root root   9 Mar 20 22:58 pci-0000:00:14.0-usb-0:7:1.0-scsi-0:0:0:0 -> ../../sdc
lrwxrwxrwx 1 root root  10 Mar 20 22:58 pci-0000:00:14.0-usb-0:7:1.0-scsi-0:0:0:0-part1 -> ../../sdc1
lrwxrwxrwx 1 root root  10 Mar 20 22:58 pci-0000:00:14.0-usb-0:7:1.0-scsi-0:0:0:0-part2 -> ../../sdc2
```

what

... apparently this is a [known issue](https://github.com/eudev-project/eudev/issues/242) --
it's been broken for years and no one has noticed.

(I am made to understand that this is not the only thing that has not kept in sync between eudev and systemd udev.)

Compare [systemd `udev-builtin-path_id.c`](https://github.com/systemd/systemd/blob/main/src/udev/udev-builtin-path_id.c)
with [eudev `udev-builtin-path_id.c`](https://github.com/eudev-project/eudev/blob/master/src/udev/udev-builtin-path_id.c)

## Idea: do this once at boot

This is a hack, but I could use the logic I wrote for finding devices by PCI path,
and run it in an init script once at boot,
and use it to symlink the correct hardware device to like `/dev/psyopsOS/ceph-disk-1` or something.

This is fine for any use case I can think of right now,
because I don't expect to hotplug devices in psyopsOS machines ever.
But that could change, which is annoying.

I could at least do this just for the Ceph disk;
I don't have to rely on the hacky init script thing for all my disks
(I can use my Python logic for anything that gets configured in progfiguration).

## Tried custom udev rules

Stuff like:

```udev
KERNEL=="sd*", SUBSYSTEM=="block", ENV{ID_TYPE}=="disk", ENV{ID_PATH}=="pci-00:17.0", SYMLINK+="psyTEST"
```

This hasn't worked though and I'm not sure if eudev doesn't support ID_PATH or if I'm doing something wrong.

## Fallback plans

* Do nothing. Maybe this won't bite me.
* Rely on `/dev/disk/by-id`. Annoying bc replacing the disk means I have to boot once to find the ID of the new disk, and bc its totally separate for each node; nodes with similar hardware can't share configuration.

## What is a devd, and what are the options?

A devd handles device creation, and is basically required on linux for dealing with hot plug like USB.

* mdev is from busybox
* original udev is now merged into systemd, and not available on Alpine
* eudev is a Gentoo project, a fork of udev pre systemd merge -- but it isn't kept up to date very well as noted
* mdevd is some other project by the s6 developer, it is a fork of mdev that provides a more efficient daemon mode to mdev's built-in daemon mode and other improvements, and can be used with something called libudev-zero which promises to offer udev features but from what I can tell is not complete -- I didn't try this one much, I just read about it

All the options are fucking bad.

### How do mdev scripts get called?

* Useful comment in mdev source that explains how mdev reads mdev.conf to execute scripts for add/remove events
  <https://github.com/brgl/busybox/blob/master/util-linux/mdev.c#L103>
* Examples: <https://github.com/slashbeast/mdev-like-a-boss>


## References

### PCI slot based device names are not necessarily stable

<https://utcc.utoronto.ca/~cks/space/blog/linux/PCINamesNotStable?showcomments>

> The resulting reality is that your PCI based names are only stable if you change no hardware in the system. The moment you change any hardware all bets are off for all hardware. You may get lucky and have some devices keep their current PCI names but you may well not. And I don't think you're necessarily protected against perverse things like two equivalent devices swapping names (or at least one of them winding up with what was the other's old name).
>
> If I'm reading lspci output correctly, what is really going on is that an increasing number of things are behind PCI bridges. These things create additional PCI buses (the first two digits in the PCI device numbering), and some combination of Linux, the system BIOS, and the PCI specification doesn't have a stable assignment for these additional busses.

### 2022/2023 Alpine Linux changes to mdev, eudev

As of March 2023, in the past few months, Alpine has made significant changes to its dev daemons (mdev, udev, etc),
and there has been busy discussion about future changes.

[main/mdevd: make it a fully supported alternative to mdev](https://gitlab.alpinelinux.org/alpine/aports/-/merge_requests/34459)
discusses demoting busybox mdev to be merely one option of many.

Spawned [ main/busybox-initscripts: add entries to /dev/disk/by-* ](https://gitlab.alpinelinux.org/alpine/aports/-/merge_requests/32330).
This adds `by-id` and `by-label` in `/dev/disk`, but doesn't add `by-path`.
It was eventually merged in [the `mdev-conf` repo](https://gitlab.alpinelinux.org/alpine/mdev-conf/-/merge_requests/2).

in the future, they're considering other changes to busy box, init scripts, etc, [see also](https://gitlab.alpinelinux.org/alpine/tsc/-/issues/52), [and this](https://gitlab.alpinelinux.org/alpine/tsc/-/issues/55).

There is some reference to that in [these chatlogs](https://irclogs.alpinelinux.org/%23alpine-linux-2022-08.log).

### Alpine Linux IRC conversation

Talked to some people in #alpine-linux on 20230321.
The outcome wasn't encouraging :(

* the user `minimal` has a similar need for cloud-init images
  <https://github.com/dermotbradley/create-alpine-disk-image>
* they did some work to get by-XXX stuff merged into Alpine mdev config
* however Alpine didn't accept them bc the same thing isn't supported in eudev
* which means that users could use this feature, switch to eudev, and then break their system
* and mdev is the default so all the other options should support what it supports
* "that was the feedback I received earlier when I was adding by-* entries", they tell me

so. we can't just make scripts for mdev and submit them bc eudev doesn't support it;
apparently eudev support has been broken for AGES, and is far out of sync with upstream systemd

### Background links etc

* Good deep magic on /dev, udev, etc in [this SE post](https://unix.stackexchange.com/questions/161674/are-there-alternatives-to-using-udev)
* Good docs on what a device manager is, while describing eudev: <https://wiki.gentoo.org/wiki/Eudev>
* This is the udev code that builds the strings for by-path, maybe I should just adapt to shell and submit a PR
  <https://github.com/systemd/systemd/blob/main/src/udev/udev-builtin-path_id.c>.
  It says `* Logic based on Hannes Reinecke's shell script` at the top, maybe I can find that and use as a starting point.
    * ... I spent some time looking to this, and it seems like it's 15 years old or more. I haven't been able to find it in the systemd repo (which has imported the entire udev repo source).
    * the modern systemd does this in C. You set rules that reference `ID_PATH`,
      which is built in the function `builtin_path_id()`.
* udev was merged into systemd in 2012 <https://lwn.net/Articles/490578/>
* it is weird to think one could "mdev like a boss", but that doesn't stop this guy <https://github.com/slashbeast/mdev-like-a-boss>
