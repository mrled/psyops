# How to mount a psyopsOS image in Docker

On a host system:

```sh
docker run --privileged -it --rm -v "$PWD/artifacts:/artifacts" alpine:latest sh
```

In the docker container

```sh
apk add losetup multipath-tools dosfstools e2fsprogs
losetup --find --show --partscan /artifacts/aarch64/psyopsOS.aarch64.wirefield.img
kpartx -av /dev/loop0
mkdir /mnt/boot /mnt/secret /mnt/a /mnt/b
mount /dev/mapper/loop0p1 /mnt/boot
mount /dev/mapper/loop0p2 /mnt/secret
mount /dev/mapper/loop0p3 /mnt/a
mount /dev/mapper/loop0p4 /mnt/b
```
