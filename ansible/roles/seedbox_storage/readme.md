# seedbox_storage

## Initial setup in 2024

* Encrypt each disk
  * cryptsetup luksFormat /dev/sdX
  * cryptsetup open /dev/sdX sdX_encrypted
  * <enter a password. I put the pw in 1pass>
* Set up automatic decryption at boot
  * dd if=/dev/urandom of=/etc/seedbox_vg_keyfile bs=1024 count=4
  * for each sdX:
    * cryptsetup luksAddKey /dev/sdX /etc/seedbox_vg_keyfile
    * echo "encrypted_device /dev/sdX /etc/seedbox_vg_keyfile luks" >>/etc/crypttab
* Create vg
  * for each sdX:
    * pvcreate /dev/mapper/sdX_encrypted
  * vgcreate seedbox /dev/mapper/sdX_encrypted /dev/mapper/sdY_encrypted ...
* Create a raid10 lv
  * lvcreate -l 100%FREE -m1 -n media seedbox /dev/mapper/sdX_encrypted /dev/mapper/sdY_encrypted ...
  * mkfs.ext4 /dev/seedbox/media
    * echo "/dev/seedbox/media /mnt/seedboxmedia ext4 defaults 0 2" >/etc/fstab

Later: adding more disks
* Encrypt each new disk
  * cryptsetursyp open /dev/sdQ sdQ_encrypted
  * ... etc see above
* Extend the volume group
  * vgextend seedbox /dev/mapper/sdQ_encrypted /dev/mapper/sdP_encrypted
* Extend the volume
  * lvextend -l +100%FREE /dev/seedbox/media
  * resize2fs /dev/seedbox/media # can be done online!

Adding more mirrors does not re-stripe existing data, which for this data is good.