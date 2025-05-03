---
title: Storage options
---

* **Block**: A raw block device that a container can use;
  these will be RWO or ReadWriteOnce,
  which means only one container can have it mounted read/write at a time.
* **Filesytem**: A shared filesystem like NFS;
  these are RWX or ReadWriteMany,
  which means that multiple containers can have it mounted read/write.
* **Object**: HTTP storage, typeically with an S3-compatible API.

[Ceph]({{< ref "ceph" >}}) does block, object, AND filesystem storage.

## Block storage

* Longhorn is a little easier to get started with, and we did use it originally,
  but it is less flexible.
  It uses free disk spaces on an existing filesystem.
  (Is there a performance penalty for that?)
* Ceph is more mature, and more featureful.
  It offers block, object, and filesystem storage.
  It can use raw storage in various formats;
  we use raw block devices here.
  SUPER complicated.
* OpenEBS: ?
* SeaweedFS: ?
* Others?

## Object storage

Minio looks cool, and I have heard it is less complex than Ceph.
However, its recommended storage driver `directpv`
[cannot be installed via CI/CD](https://github.com/minio/directpv/issues/436).

Ceph doesn't have this limitation, so we're using it for now.