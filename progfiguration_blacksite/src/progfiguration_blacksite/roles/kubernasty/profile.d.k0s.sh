#!/bin/sh
alias kubectl="/usr/local/bin/k0s kubectl"
alias k="/usr/local/bin/k0s kubectl"
if test -r /var/lib/k0s/pki/admin.conf; then
    export KUBECONFIG="/var/lib/k0s/pki/admin.conf"
fi
