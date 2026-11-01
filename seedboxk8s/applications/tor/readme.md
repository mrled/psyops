# In-cluster tor

## Tor image updates

The `cicd/torproxy-build` CronJob rebuilds the private Tor image daily
at 03:37 America/Chicago, installing current Debian Tor packages.
Renovate then checks the published `latest` image on its hourly run,
pins its digest, and automerges digest changes for the Tor deployment.
Rebuilding is necessary: Renovate cannot update packages inside an existing image.

The deployment temporarily uses unpinned `latest` to replace the obsolete Tor image.
The next successful Renovate run restores a digest pin.
Future builds do not affect the running deployment until the digest-update PR merges.

To rebuild immediately, create a job from `cronjob/torproxy-build` in namespace `cicd`.
Avoid overlapping manual and scheduled builds, since both publish the same tag.
After deployment, check Tor's logs for `Bootstrapped 100%` and verify the Gatus checks.

## Components

* `torproxy` container: runs Tor itself with a SOCKS5 proxy on port 9050.
* `torprivoxy` container: runs Privoxy, which acts as an HTTP proxy that forwards requests to SOCKS;
  some applications support HTTP proxies but not SOCKS proxies.
* `onionproxy` container: an **UNSAFE** nginx server that will return onion results from a local subdomain,
  so that non-onionized applications can make simple HTTP requests and get back onion results,
  e.g. by requesting a resource at `http://something.onion.example.com`,
  this proxy will return results for `http://something.onion`.
  **THIS IS UNSAFE** especially for browsers but really for anything,
  because the results might include JavaScript and other resources that reference the non-onion web and could deanonymize the client.
  It's also not good for browsing because `.onion` links are not transformed to `.onion.example.com` links,
  so clicking on the links (or requesting any returned absolute URL to images or other resources) will not work.
  Why even have this? It's basically for z-library in lazylibrarian.
