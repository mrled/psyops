# seedbox

## Troubleshooting notes

Note: to redeploy without running this role, run:

    docker stack deploy -c /etc/seedbox/seedbox.compose.yml seedbox

If a container is failing, use `docker service logs seedbox_SERVICENAME` to see the logs from the failed containers

## Plex setup

May need to hit the 32400 port directly.

    ssh username@ip_of_server -L 32400:localhost:32400 -N

Then browse to `http://localhost:32400`

## Authentication

Based on <https://geek-cookbook.funkypenguin.co.nz/ha-docker-swarm/traefik-forward-auth/dex-static/>

## Dex theme

For the Dex theme, I copied the stylesheet from the light theme on the Dex container.
That was at /srv/dex/web/themes/light.
Then I add custom logo.png and favicon.png along with that stylesheet,
and mount that as a volume at /srv/dex/web/themes/mindcontrol.

Icon from <https://thenounproject.com/search/?q=illuminati&i=3884008>

## App configuration

App configuration is mostly done manually in the admin UI for the apps.
For this reason backups are important.
I back /etc/seedbox up to wasabi, encrypted, via duplicity.

Some important configuration:

* Connect the *arr apps and sabnzbd/rtorrent, etc
* Configure Jackett
* Use `remote path mapping` in *arr apps for rtorrent, because rtorrent downloads to /downloads while sabnzbd downloads to /media.
  <https://trash-guides.info/Sonarr/Sonarr-remote-path-mapping/>