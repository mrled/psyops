# Raspberry Pi and psyopsOS

## Partition labels

U-Boot is too fucking stupid to understand partition labels.
We use a a horrible awesome hack instead:
each side has a file with the name of the label on it.
So the A side has a file called `psyopsOS-A`
and the B side has a file called `psyopsOS-B`.

U-Boot can chuck a file with a given name into RAM easily.
We can enumerate all partitions on all storage,
try to find a file with the A name,
and if it succeeds we know that's the A partition.
Same for B.

WARNING: in `neuralupgrade.firmware.rpi.rpi_cfg` there are references to boot labels, but U-Boot cannot underrstand them!
This is really just these stupid files named with the A or B name, not real partition labels

## U-Boot

We need to build our own U-Boot.
Alpine does package one as `u-boot-raspberrypi`, but it doesn't include serial output.

On macOS, you can build the configuration with:

```sh
brew install make bison flex dtc
git clone https://source.denx.de/u-boot/u-boot
cd u-boot
git checkout v2025.01 # or whatever tag you want

# Generate the default Pi 4 configuration
/opt/homebrew/opt/make/libexec/gnubin/make rpi_4_defconfig

# Adjust it:
/opt/homebrew/opt/make/libexec/gnubin/make menuconfig
```

TODO: finish this
