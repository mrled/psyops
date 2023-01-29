# Kubernasty cluster environment variables and functions for dot-sourcing.

export KUBECONFIG=/secrets/psyops-secrets/kubernasty/kubeconfig.yml

export SOPS_AGE_RECIPIENTS=age1869u6cnxhf7a6u6wqju46f2yas85273cev2u6hyhedsjdv8v39jssutjw9
export SOPS_AGE_KEY_FILE=/secrets/psyops-secrets/kubernasty/kubernasty-sops.age

# Examine certificates using openssl
certinfo() {
    hostname="$1"
    echo "" |
        openssl s_client -showcerts -servername "$hostname" -connect "$hostname":443 2>/dev/null |
        openssl x509 -inform pem -noout -text
}

# Show the issuing CA for a remote server
# With this you can tell if a cert was issued by:
# - the Traefik default self-signed cert, which returns something like `Issuer: CN=TRAEFIK DEFAULT CERT`
# - the Let's Encrypt staging CA, which returns somethign like `Issuer: C=US, O=(STAGING) Let's Encrypt, CN=(STAGING) Artificial Apricot R3`
# - the LE prod CA, which returns something like `Issuer: C=US, O=Let's Encrypt, CN=R3`
certissuer() {
    certinfo "$1" | grep 'Issuer: '
}
