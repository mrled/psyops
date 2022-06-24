# psyopsOS networking

## Custom NIC name

We use `psy0` for the main psyopsOS NIC.

- This means we can rely on the NIC called `psy0` everywhere
- For instance, kube-vip running as a DaemonSet needs to have the same NIC name on all k3s cluster nodes

We do this by creating a separate `mactab` file for each host.
See [System secrets and individuation](./system-secrets-individuation.md) for more info.
