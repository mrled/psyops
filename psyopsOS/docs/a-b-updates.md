## A/B Updates

TODO: document how this works. Here is a dump from the todo file before it was implemented.

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
        * Extraction while downloading is useful for one-off updates from a trusted controller node (my laptop), but can't be permitted for updates from the `pysops.micahrl.com` server, which we are treating as untrusted.
        * We will probably wait to implement extraction while downloading until later, but use a tarball for this for the moment.
        * For updates from `psyops.micahrl.com`, we will expect to first download a copy of the manifest, signature, and tarball, verify the signature, then the manifest with the signature, and then hash the tarball to make sure it matches what's in the manifest.
    * How will we version these?
        * We don't have to force this to fit into pip or some other fuckhead versioning system, we use datestamps like 20240126-212806.
        * Stored in the S3 bucket as e.g. `img/grubusb/VERSION/manifest.json`
        * Manifest includes version (again, so it's useful when downloaded locally), full URL to tarball, and tarball checksum
        * Manifest file is signed with minisign. We don't have to sign the tarball, it's verified by checksum from the signed manifest.
        * To get the latest version, use S3 Object Redirect with a `img/grubusb/latest/manifest.json`
            * Object Redirect only works with objects, not folders
            * We could add Object Redirect to `tarball.tar` and `signature.minisign` (or whatever), so that the client just pulls from `latest` every time. This isn't atomic tho, and I guess a bug could cause it to go out of sync.
            * Or we can use e.g. `"repopath": "https://psyops.micahrl.com/img/grubusb/VERSION/", "tarball": "tarball.tar", ...` to the `manifest.json`. This lets `manifest.json` use relative paths (`"tarball": "tarball.tar"`), which will continue to work when downloaded locally, but it bakes the repo into the manifest, which is less flexible to changine the repo URL or something.
        * Actually, what if we did this: keep the version (which is a date) in the filename; use an out of band signature file that contains the filename; only have a `latest` for the signature file.
            * The client will have to download the update and its signature in two requests under any scheme we're considering anyway
            * If the version and date are already recorded in the filename, there's no reason for the manifest file to exist.
            * The client fetches the `latest` signature FIRST, and then fetches whatever filename is specified in the signature, and then verifies. This means that updates are atomic (at least assuming adding the S3 Object Redirect is atomic), since even if the `latest` signature gets replaced after the client fetches it, it will fetch the actual update by name.
            * The version number also must be kept on the partition, so that some sort of update check can be made. Probably save the version in the tarball at build time. Or maybe the updater does it -- place a `version.json` or something on the filesystem when it applies the update, including the version and date applied.
        * Do we need to release psyopsOS + efisys together in a bundle? I am assuming no.
    * Verification
        * I wanted to use minisign because that's what all the cool kids use.
        * However, the fucking thing only works with private key FILES signing other FILES. There is no way to provide a private key via a string, and no way to sign arbitrary data without writing it to a file first.
        * I guess the minisign way isn't totally impossible to work, it's just clunky, and I don't love saving private keys to disk for signing. They do stay encrypted so maybe... I save them to disk encrypted, then pull the password out of the secret store and provide that at runtime.
        * It would be nice if we could securely, incrementally, and atomically download and write updates without first downloading to tmp storage then verifying then applying. To do this would require more sophistication than I have tho. I think you can use existing cryptographic ideas to build something like this but I'm not aware of anything off the shelf. Maybe "streaming verification" is a thing, maybe we chunk verification, or something like a merkel tree. But I think all of these would require custom tooling.
        * Alpine appears to use RSA keys from OpenSSL for signing APK packages. Maybe I just do this. Or something that uses high level Python `cryptography` functions.
