# seedbox

## Troubleshooting notes

Note: to redeploy without running this role, run:

    docker stack deploy -c /etc/seedbox/seedbox.compose.yml seedbox

If a container is failing, use `docker service logs seedbox_SERVICENAME` to see the logs from the failed containers

## Plex setup

May need to hit the 32400 port directly.

    ssh username@ip_of_server -L 32400:localhost:32400 -N

Then browse to `http://localhost:32400`