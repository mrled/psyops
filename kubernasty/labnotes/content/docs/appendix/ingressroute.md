---
title: IngressRoute
---

* Kubernetes has a generic resource called `Ingress`.
    * Traefik supports `Ingress`, but has a more natural extension called `IngressRoute`. It's unclear to me what the differences are.
    * (The `IngressRoute` name is also used by other proxies that work with Kubernetes, but its nonstandard, and each project's `IngressRoute` is completely different and incompatible.)
    * <https://stackoverflow.com/questions/60177488/what-is-the-difference-between-a-kubernetes-ingress-and-a-ingressroute>
    * > Ingress is a shared abstraction that can be implemented by many providers (Nginx, ALBs, Traefik, HAProxy, etc). It is specifically an abstraction over a fairly simple HTTP reverse proxy that can do routing based on hostnames and path prefixes. Because it has to be a shared thing, that means it's been awkward to handle configuration of provider-specific settings. Some teams on the provider side have decided the benefits of a shared abstraction are not worth the complexities of implementation and have made their own things, so far Contour and Traefik have both named them IngressRoute but there is no connection other than similar naming.
* Traefik's built in Let's Encrypt support works fine with its `IngressRoute`, but Cert Manager cannot work with `IngressRoute`. To use Cert Manager, you need to use `Ingress` instead.
    * <https://doc.traefik.io/traefik/providers/kubernetes-crd/>
    * > If you want to keep using Traefik Proxy, high availability for Let's Encrypt can be achieved by using a Certificate Controller such as Cert-Manager. When using Cert-Manager to manage certificates, it creates secrets in your namespaces that can be referenced as TLS secrets in your ingress objects. When using the Traefik Kubernetes CRD Provider, unfortunately Cert-Manager cannot yet interface directly with the CRDs. A workaround is to enable the Kubernetes Ingress provider to allow Cert-Manager to create ingress objects to complete the challenges. Please note that this still requires manual intervention to create the certificates through Cert-Manager, but once the certificates are created, Cert-Manager keeps them renewed.
    * Note that this means that you have to define your own certificates when spinning up new services. This isn't that bad; you're already writing a gigantic blob of YAML to write the various namespace/service/secret/ingress manifests, you might as well add one more fucking blob of YAML for the cert too. The whole point of computers is to enable humans to write more YAML, and this is just another way to accomplish this goal.
* It's worth mentioning there is a _new_ thing called the Kubernetes `Gateway`
    * It is a first party resource like `Ingress`
    * It's more generic than `Ingress`, hopefully solving the problems that Traefik tries to solve with its proprietary `IngressRoute`
    * Support is in progress for Traefik, Cert Manager, ExternalDNS... most things are expected to support it since it will become standard
    * It seems too early right now, things are still rough, e.g. Traefik's support is still "experimental"
