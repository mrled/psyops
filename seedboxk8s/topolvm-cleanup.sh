#!/bin/bash
# Check all topolvm LVs on disk vs Kubernetes, and whether each is mounted.
set -eu

K8S_LVS=$(/usr/local/bin/k0s kubectl get pv -o json | jq -r '
  .items[]
  | select(.spec.csi.driver? == "topolvm.io")
  | .spec.csi.volumeHandle')

echo "=== Topolvm LV audit for 'seedbox' VG ==="
{
  printf 'NAME\tSIZE\tMOUNTED\tPVC\n'
  while read lv_name lv_size dm_path; do
    if test "$lv_name" = "media"; then
      continue
    fi
    if mount | grep -q "$lv_name"; then
      mounted="yes"
    else
      mounted="no"
    fi

    # This is a little slow, especially for the big 'media' LV that we skip
    ls="$(debugfs -R 'ls -p /' "$dm_path" 2>/dev/null | wc -l)"

    if echo "$K8S_LVS" | grep -qF "$lv_name"; then
      pvc=$(/usr/local/bin/k0s kubectl get pv -o json | jq -r --arg h "$lv_name" \
        '.items[] | select(.spec.csi.volumeHandle == $h) | "\(.spec.claimRef.namespace)/\(.spec.claimRef.name)"')
      printf '%s\t%s\t%s\t%s\t%s\n' "$lv_name" "$lv_size" "$mounted" "$pvc" "$ls"
    else
      printf '%s\t%s\t%s\t-\t%s\n' "$lv_name" "$lv_size" "$mounted" "$ls"
    fi
  done < <(lvs --noheadings -o lv_name,lv_size,lv_dm_path "seedbox" 2>/dev/null)
} | column -t -s $'\t'
