# Operating system updates

It would be nice to make this easier in the future.
For now it's manual.

- Confirm that the image is mounted to `/media/sdb` (TODO: how can I automate this?)
- Copy the new iso over the network
- Run these commands:

```sh
umount /.modloop
umount /media/sdb
dd if=/tmp/alpine-psyopsOS-0x001-x86_64.iso of=/dev/sdb
```

- Reboot
