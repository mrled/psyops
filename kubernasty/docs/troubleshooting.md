# Troubleshooting

jesus h christ this is the most insane system i've ever seen in my life

## What does 'Evicted' mean?

```
> kubectl get pods -A
NAMESPACE      NAME                                       READY   STATUS      RESTARTS        AGE
cert-manager   cert-manager-6544c44c6b-tlrn9              1/1     Running     0               139m
cert-manager   cert-manager-cainjector-5687864d5f-g4275   1/1     Running     0               139m
cert-manager   cert-manager-webhook-785bb86798-xd264      1/1     Running     0               139m
kube-system    coredns-d76bd69b-ktqlt                     1/1     Running     0               3h52m
kube-system    helm-install-traefik-crd-knpq4             0/1     Completed   0               3h52m
kube-system    helm-install-traefik-w9gx2                 0/1     Completed   0               10m
kube-system    kube-vip-ds-4s9q2                          1/1     Running     2 (3h25m ago)   3h52m
kube-system    kube-vip-ds-pc4fk                          0/1     Evicted     0               6m56s
kube-system    kube-vip-ds-q64tw                          1/1     Running     0               3h23m
kube-system    local-path-provisioner-6c79684f77-t4lqd    1/1     Running     0               3h52m
kube-system    metrics-server-7cd5fcb6b7-dsdmd            1/1     Running     0               3h52m
kube-system    svclb-traefik-27gq9                        0/2     Evicted     0               6m56s
kube-system    svclb-traefik-hmlhp                        0/2     Pending     0               10m
kube-system    svclb-traefik-vghh6                        2/2     Running     0               14m
kube-system    traefik-5f4f7f44c5-zc8r6                   1/1     Running     0               10m
whoami         whoami-5d4d578786-zjmj5                    1/1     Running     0               3h1m
```

You can investigate this with `kubectl describe`.

```
> kubectl describe pods --namespace kube-system kube-vip-ds-pc4fk | less

# ... shows a bunch of output, with this at the bottom:

Events:
  Type     Reason     Age   From               Message
  ----     ------     ----  ----               -------
  Normal   Scheduled  8m1s  default-scheduler  Successfully assigned kube-system/kube-vip-ds-pc4fk to kenasus
  Warning  Evicted    8m1s  kubelet            The node had condition: [DiskPressure].
```

From there, I ssh'd to kenasus and saw that indeed / was full.
When I fixed that problem, kube-vip and svclb-traefik pods automatically started on that host.

See also:

* <https://www.padok.fr/en/blog/kubernetes-pods-evicted>
