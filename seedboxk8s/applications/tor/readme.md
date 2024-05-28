# In-cluster tor

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
