#!/bin/sh
set -eu

# Back up config directories for Docker Swarm services.
# Create a tarball for each service which init containers will use to restore the config.
# Just used for initial data import from Docker Swarm -> Kubernetes.

overwrite=
confdir=/seedboxmedia/seedboxconf

# Everything we care about:
# tobackup="cops ersatztv heimdall hydra2 jackett lazylibrarian lidarr plex radarr sabnzbd shhh sonarr stash tautulli transmission"
# Just the smaller ones for testing:
tobackup="cops ersatztv heimdall hydra2 jackett lazylibrarian radarr sabnzbd shhh sonarr stash tautulli transmission"
# Everything:
# 2.5M	/seedboxmedia/seedboxconf/cops
# 44M	/seedboxmedia/seedboxconf/ersatztv
# 16M	/seedboxmedia/seedboxconf/heimdall
# 649M	/seedboxmedia/seedboxconf/hydra2
# 23M	/seedboxmedia/seedboxconf/jackett
# 19M	/seedboxmedia/seedboxconf/lazylibrarian
# 6.8G	/seedboxmedia/seedboxconf/lidarr
# 9.3G	/seedboxmedia/seedboxconf/plex
# 13M	/seedboxmedia/seedboxconf/prowlarr
# 330M	/seedboxmedia/seedboxconf/radarr
# 30M	/seedboxmedia/seedboxconf/sabnzbd
# 28K	/seedboxmedia/seedboxconf/seedbox.compose.yml
# 35M	/seedboxmedia/seedboxconf/shhh
# 159M	/seedboxmedia/seedboxconf/sonarr
# 17M	/seedboxmedia/seedboxconf/stash
# 60M	/seedboxmedia/seedboxconf/tautulli
# 204K	/seedboxmedia/seedboxconf/transmission


padlen=16

mkdir -p /seedboxmedia/seedboxconf/backups/migr8tok8s
for service in $tobackup; do
    svcdir="$confdir/$service"
    paddedsvc=$(printf "%${padlen}s" "$service")
    tarball="/seedboxmedia/seedboxconf/backups/migr8tok8s/$service.tar.gz"
    if test "$overwrite" || test ! -e "$tarball"; then
        echo -n "Backing up        $paddedsvc...       "
        if ! tar -czf "$tarball" -C "$svcdir" .; then
            echo "Failed to back up $service"
            rm -f "$tarball"
            exit 1
        fi
    else
        echo -n "Already backed up $paddedsvc...       "
    fi
    du -sh "$tarball"
done
