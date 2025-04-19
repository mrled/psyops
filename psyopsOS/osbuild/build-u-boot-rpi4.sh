#!/bin/sh
set -eux

script=$(basename "$0")

# Default argument values
config=
outdir=
version=2025.04

usage() {
    cat <<ENDUSAGE
$script: Build U-Boot for Raspberry Pi 4
Usage: $script [-h] [OPTIONS ...]

ARGUMENTS:
    -h                      Show this help message
    -c CONFIG               U-Boot config file created with `make menuconfig`
                            (required)
    -o OUTPUTDIR            Output directory
                            (required)
    -V VERSION              U-Boot version to use
                            (default: $version)

Required packages:
bash bc build-base bison flex git gnutls-dev ncurses-dev openssl-dev

When starting from scratch:
- Start with `make rpi_4_defconfig`
- Then run `make menuconfig` to set the config options you want on top of that
- Pass the resulting .config to this script with -c

About U-Boot and Device Tree:
- See also: <https://docs.u-boot.org/en/latest/develop/devicetree/control.html>
- U-Boot pulls device tree source files from the kernel source tree via a git submodule;
  it will build e.g. arch/arm/dts/bcm2711-rpi-4-b.dtb
- It does NOT build normal Raspberry Pi overlays like disable-bt.dtbo.
  However, we need disable-bt.dtbo to be present on the boot partition
  so that the VideoCore firmware can use it;
  it somehow knows from disable-bt.dbto to configure GPIO pins
  for serial instead of Bluetooth (pin muxing).
ENDUSAGE
}

while test $# -gt 0; do
    case "$1" in
    -h) usage; exit 0;;
    -c) config="$2"; shift 2;;
    -o) outdir="$2"; shift 2;;
    -V) version="$2"; shift 2;;
    -*) echo "Unknown option: $1; see '$script -h'" >&2; exit 1;;
    *) echo "Unknown argument: $1; see '$script -h'" >&2; exit 1;;
    esac
done

for arg in "$outdir"; do
    if test -z "$arg"; then
        echo "Missing required argument(s); see '$script -h'" >&2
        exit 1
    fi
done

ubdir="u-boot-$version"
ubtar="u-boot-$version.tar.bz2"
ubtarpath="$outdir/$ubtar"
if ! test -e "$ubtarpath"; then
    wget -O "$ubtarpath" https://ftp.denx.de/pub/u-boot/u-boot-$version.tar.bz2
fi

mkdir /tmp/build
cd /tmp/build
tar jxf "$ubtarpath"
cd "$ubdir"


# cp "$config" ./u-boot/.config
# # Required for it to recognize the config file we just copied in
# make olddefconfig

make rpi_4_defconfig
scripts/config --enable CONFIG_CMD_BOOTMENU
# After running scripts/config, we have to run make olddefconfig again
make olddefconfig

make -j$(nproc)

echo "Building U-Boot finished"
ls -alF
find . -type f -name '*.dtb'
find . -type f -name '*.dtbo'

mkdir -p "$outdir"
cp ./u-boot.bin "$outdir"/u-boot.bin
cp ./.config "$outdir"/u-boot.config
cp ./dts/dt.dtb "$outdir"/dt.dtb
# cp ./arch/arm/dts/bcm2711-rpi-4-b.dtb "$outdir"/bcm2711-rpi-4-b.dtb
echo "$version" > "$outdir"/u-boot.version

echo "U-Boot built and copied to $outdir"
