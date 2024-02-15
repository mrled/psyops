# A/B Updates

psyopsOS can apply A/B operating system updates.
The work has been done for x86_64;
I think something similar should work for Raspberry Pi but I haven't looked deeply into it.

Images are built with `tk mkimage diskimg`.
This calls `neuralupgrade apply ...` behind the scenes.
It creates a disk image with four labeled partitions:

1. `PSYOPSOSEFI`: The EFI System Partition, containing GRUB and maybe some EFI programs like memtest.
2. `psyops-secret`: A secrets partition, which might contain a particular machine's secrets, or blank and suitable for booting up and configuring later
3. `psyopsOS-A`: An OS partition
4. `psyopsOS-B`: An OS partition

The OS partitions are not root filesystems,
they store a kernel and initramfs for booting,
a modloop containing kernel modules (that doesn't require loading them into RAM),
a squashfs for read-only root filesystem,
and some supporting files like a System.map, boot/ directory, version files, etc.

GRUB is configured to boot either the A or B partition by default,
but either is accessible from the GRUB menu.
When booting, GRUB passes the partition label via kernel command line like `psyopsos=psyopsOS-A`,
so this is visible from a booted system's `/proc/cmdline`.

A system can apply an OS upgrade with `neuralupgrade apply nonbooted`.
That verifies the signature of an OS upgrade tarball,
extracts the upgrade tarball to the nonbooted partition,
and upgrades the GRUB configuration on the EFI System Partition to boot from the upgraded partition.
It transparently handles mounting partitions read-write and unmounting them when finished.

We can also apply EFI System Partition updates.
`neuralupgrade` knows to run `grub-install`,
and we also build tarballs that (at least for now) just contain EFI programs like memtest,
which `neuralupgrade` can apply with `neuralupgrade apply efisys`.
When `neuralupgrade` changes the GRUB configuration,
whether that's in applying an update to the nonbooted side,
or applying an efisys upgrade,
or any other time,
it does so as carefully as possible.
We don't get true atomiticity from the FAT32 EFI system partition,
but we do keep backups of old GRUB configurations,
write the new configuration out to a new file,
and move the new version into the `grub.cfg` filename
to minimize the chances of an inconsistent write.
It's not perfect, but it's the best we can do given FAT32.
And I find myself in [good company](https://crawshaw.io/blog/jsonfile).

Updates are verified with `minisign`.
We use minisign's trusted comments feature for a few key=value pairs.
Here's an example from a recent local build:

```text
> cat artifacts/psyopsOS.tar.minisig
untrusted comment: signature from minisign secret key
RURFlbvwaqbpRhKh+8bfF/6FT1eyY0TTzStsYXjDM6w6VbVrmXvi+rWDM01apVH0BHphsTFNrE15r8LbmZuCe9BcWBm3AQBPiwQ=
trusted comment: psyopsOS filename=psyopsOS.20240202-212117.tar version=20240202-212117 kernel=6.1.75-0-lts alpine=3.18
HxZ9wysLaUZZJTgxQKtwlBMZIRtTaH4Q6Y5zyVOhwVaSMPmDZk2IInPm3uZH+2gSdxuGkiRF1CV68y7w/5ahCg==
```

Note that the signature file is `psyopsOS.tar.minisig`,
and indeed it was created from a psyopsOS tarball called `psyopsOS.tar`,
but the trusted comment includes
`filename=psyopsOS.20240202-212117.tar`.
That `filename` value is something we embed ourselves, and is totally meaningless to minisign.
(Actually, minisign generates a default trusted command with a `filename`,
but minisign doesn't use that during verification.)
It also includes a `version` (which is just a build date),
and a kernel and alpine version string.
We can use all of these to provide information about the contents of an update,
and we even copy this signature file to the OS partition after extracting the OS tarball there.

We use the `filename` in a couple of useful ways.
For one, it's useful for the build scripts to create the OS tarball in a known location
without a versioned filename,
so that other build steps can use it.
More interesting is how it will help with clients pulliing updates over HTTP.
`neuralupgrade` doesn't yet support HTTP update repositories,
but it will soon.
When it does, it will request a file like `https://psyops.micahrl.com/os/latest.minisig`.
This will point to a file with an actual name like `psyopsOS.20240202-212117.tar.minisig`,
but it'll use S3 Object Redirect so a separate HTTP request is not required.
We don't need to have a `latest.tar`,
because the minisig contains the filename.
This prevents a race condition between uploading a new tarball and a client trying to upgrade its nonbooted partition.
And because the first thing we pull is the signature,
which is validated by a public key on each client,
the update process is secured.
