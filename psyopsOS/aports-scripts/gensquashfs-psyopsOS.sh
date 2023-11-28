#!/bin/sh -e

usage() {
	cat <<ENDUSAGE
$(basename "$0"): Generate a psyopsOS SquashFS image
Usage: $(basename "$0") [-h] [-a ARCH] [-r REPOSITORIES_FILE] [-k KEYS_DIR] [-o OUTFILE] [APK_ADD_ARGS...]

Options:
	-h						Show this help message
	-a ARCH					Architecture to build for (required)
	-r REPOSITORIES_FILE	Repositories file to use (required)
	-k KEYS_DIR				Directory containing signing keys (required)
	-o OUTFILE				Output file name (required)
	APK_ADD_ARGS			Additional arguments to pass to apk add (including package names)
ENDUSAGE
}

cleanup() {
	rm -rf "$tmp"
}

tmp="$(mktemp -d)"
trap cleanup EXIT
chmod 0755 "$tmp"

arch="$(apk --print-arch)"
repositories_file=/etc/apk/repositories
keys_dir=/etc/apk/keys

while getopts "ha:r:k:o:" opt; do
	case $opt in
	h) usage; exit 0;;
	a) arch="$OPTARG";;
	r) repositories_file="$OPTARG";;
	k) keys_dir="$OPTARG";;
	o) outfile="$OPTARG";;
	esac
done
shift $(( $OPTIND - 1))

cat "$repositories_file"

if [ -z "$outfile" ] || [ -z "$arch" ] || [ -z "$repositories_file" ] || [ -z "$keys_dir" ]; then
	echo "Missing required arguments" >&2
	usage >&2
	exit 1
fi

echo "APK_ADD_ARGS: $@"

# Install all packages passed as APK_ADD_ARGS
${APK:-apk} add --keys-dir "$keys_dir" --no-cache \
	--repositories-file "$repositories_file" \
	--no-script --root "$tmp" --initdb --arch "$arch" \
	"$@"

# Show results
echo "================================ psyopsOS filesystem after installing apks:"
find "$tmp"

# Configure busybox
for link in $("$tmp"/bin/busybox --list-full); do
	[ -e "$tmp"/$link ] || ln -s /bin/busybox "$tmp"/$link
done

# Copy alpine-release
${APK:-apk} fetch --keys-dir "$keys_dir" --no-cache \
	--repositories-file "$repositories_file" --root "$tmp" \
	--stdout --quiet alpine-release | tar -zx -C "$tmp" etc/

# make sure root login is disabled
# sed -i -e 's/^root::/root:*:/' "$tmp"/etc/shadow
# Don't do this ... psyopsOS-base should set root password

# Find the installed version of Alpine
branch=edge
VERSION_ID=$(awk -F= '$1=="VERSION_ID" {print $2}'  "$tmp"/etc/os-release)
case $VERSION_ID in
*_alpha*|*_beta*) branch=edge;;
*.*.*) branch=v${VERSION_ID%.*};;
esac

# Set APK repositories to the installed version of Alpine
cat > "$tmp"/etc/apk/repositories <<EOF
https://dl-cdn.alpinelinux.org/alpine/$branch/main
https://dl-cdn.alpinelinux.org/alpine/$branch/community
EOF

# Squash dat FS
mksquashfs "$tmp" "$outfile" -noappend -comp xz
