#!/bin/sh
set -eu

umask 022

psyopsroot="$HOME"/psyops
aportsdir="$HOME"/aports
workdir="$HOME"/tmp/mkimage-workdir
isosdir="$HOME"/isos

psyopsosdir="$psyopsroot"/psyopsOS

# psyopsOS mkimage and genapkovl scripts expect this to be present
export PSYOPSOS_OVERLAY="$psyopsosdir/os-overlay"

cp mkimg.psyopsOS.sh genapkovl-psyopsOS.sh "$aportsdir"/scripts/

sudo rm -rf /tmp/mkimage*
sudo rm -rf "$workdir"/apkovl*
sudo rm -rf "$workdir"/apkroot*

#sudo apk update

starttime=$(date)

cd "$aportsdir"/scripts
./mkimage.sh \
    --tag 0x001 \
    --outdir "$isosdir" \
    --arch x86_64 \
    --repository http://mirrors.edge.kernel.org/alpine/v3.16/main \
    --repository http://mirrors.edge.kernel.org/alpine/v3.16/community \
    --workdir "$workdir" \
    --profile psyopsOS

endtime=$(date)

echo "Started: $starttime"
echo "Ended:   $endtime"

echo "ISO directory: $isosdir:"
ls -alF "$isosdir"
