# psyopsos-builder Dockerfile

This is used to build the Alpine ISO image inside an Alpine Docker image.

- You CANNOT mount the workdir as a local Docker volume from Docker Desktop on macOS (and probably Windows too, but untested).
    If you do, it will try to boot and then tell you that it cannot find init.
    But you can make a docker volume with `docker volume create` and use that.
    (`tasks.py` does this automatically when running `invoke mkimage`.)
    This is worth doing bc it means that rebuilds will be fast.
    However, the cache sometimes needs to be deleted (see below) -
    you can `docker volume rm` and then recreate it.
- One time I couldn't get it to build an ISO image with the kernel on it for me until I deleted the workdir?
    I got an error message like `Loading /boot/vmlinuz-lts failed: No such file or directory`,
    and when I mounted the iso there was indeed no kernel file there under that name or any other.
    I have no idea if I had done something wrong here or if it is realted to the workdir as a local Docker volume.
