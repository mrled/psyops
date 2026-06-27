#!/bin/sh
set -eu

# Apply the OpenSearch security configuration (internal_users, roles, roles_mapping, etc.)
# to a running cluster using securityadmin.sh.
#
# This is necessary because the helm chart only runs securityadmin on initial install.
# Any subsequent changes to Secret.opensearch-security-config.yaml require running this script manually
# after Flux has synced the Secret (wait ~60s for the mounted files to update).

echo "Applying security config via securityadmin.sh..."
kubectl exec -n opensearch opensearch-cluster-master-0 -- \
  /usr/share/opensearch/plugins/opensearch-security/tools/securityadmin.sh \
  -cacert /usr/share/opensearch/config/admin-tls/ca.crt \
  -cert /usr/share/opensearch/config/admin-tls/tls.crt \
  -key /usr/share/opensearch/config/admin-tls/tls.key \
  -cd /usr/share/opensearch/config/opensearch-security/ \
  -nhnv -icl

echo "Restarting OpenSearch Dashboards to pick up new opensearch_dashboards.yml..."
kubectl rollout restart deployment/opensearch-dashboards -n opensearch
echo "Dashboards restarted (startup takes several minutes, check with: kubectl rollout status deployment/opensearch-dashboards -n opensearch)"
