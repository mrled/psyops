#!/bin/sh

# Script was used to test Plex ingress, which proved tricky to get working.

set -u

echo "Pods..."
kubectl get pods -A | grep '\(plex\)\|\(traefik\)'

echo "Testing all the URLs we care about..."

# (At the time of this writing, younix.us was the cluster FQDN)

while read -r url; do
    printf "Testing \e[34m$url\e[0m... "
    result=$(wget --timeout=2 --no-check-certificate --server-response -SqHO- "$url" 2>&1)
    if test $? = 0; then
        printf "\e[32mSuccess\e[0m\n"
    else
        printf "\e[31mFailed\e[0m\n"
    fi
    echo "$result" | head
done <<EOF
https://whoami.younix.us/
http://192.168.1.25:10080/
https://plex.younix.us/
https://plex.younix.us/web/index.html
http://192.168.1.25:32400/
http://192.168.1.25:32400/web/index.html
http://192.168.1.25:64800/
http://192.168.1.25:64800/web/index.html
EOF

printf "Check from traefik container inside cluster... "
pod=$(kubectl get pods -l name=traefik-localnet -n traefik -o jsonpath='{.items[0].metadata.name}')
printf "(pod \e[34m$pod\e[0m) "
cmd="wget --timeout=2 --no-check-certificate --server-response -SqO- http://plex.tortuga.svc.cluster.local:32400/web/index.html"
result=$(kubectl exec -it -n traefik $pod -- $cmd 2>&1)
if test $? = 0; then
    printf "\e[32mSuccess\e[0m\n"
else
    printf "\e[31mFailed\e[0m\n"
fi
echo "$result" | head

printf "\n\n"
