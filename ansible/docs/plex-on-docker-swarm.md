# Plex on Docker Swarm

This is a configuration I'd like to move to.
It would mean integrating the plexserver role into the seedbox role.

## Running Plex on Swarm

See references:

* https://www.reddit.com/r/PleX/comments/ebmlxe/plex_on_docker_swarm/
* Some Jellyfin docs:
  * A PR adding more notes about Traefik:
    <https://github.com/jellyfin/jellyfin-docs/pull/168/files>
  * The full file from that change:
    <https://github.com/jellyfin/jellyfin-docs/pull/168/files>
  * The current location of that documentation:
    <https://github.com/jellyfin/jellyfin-docs/blob/master/general/networking/traefik.md>
* Bug in Traefik preventing it from auto discovering Docker service IP addresses, requires workaround:
  <https://github.com/containous/traefik/issues/5559>


## Some specifics

* The Traefik bug requires that we set an IP address for our Plex container
  (or any other container that needs host or bridged networking)
  in order for DLNA and other broadcast networking to work.
* Possible to get traefik reverse proxying TCP and UDP connections to all ports that Plex uses?
  There are a lot.
  This would be nice so that Plex could run on a multi-node swarm.
  But maybe it's not that important.

