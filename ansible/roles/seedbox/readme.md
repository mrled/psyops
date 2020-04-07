# seedbox

## Troubleshooting notes

Note: to redeploy without running this role, run:

    docker stack deploy -c /etc/seedbox/seedbox.compose.yml seedbox

If a container is failing, use `docker service logs seedbox_SERVICENAME` to see the logs from the failed containers
