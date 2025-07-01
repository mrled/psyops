#!/bin/sh
set -eu

USER="callista"
TABLE="chineseroom"
CHAIN="output"

NFT_RULESET=$(cat <<EOF
table inet $TABLE {
  chain $CHAIN {
    type filter hook output priority 0; policy accept;

    # Whitelist specific addresses
    #
    # localhost traffic on specific ports only
    # ip daddr 127.0.0.1 tcp dport {80,443,10000-11000} meta skuid "$USER" accept
    # ip6 daddr ::1 tcp dport {80,443,10000-11000} meta skuid "$USER" accept
    #
    # all localhost traffic
    ip daddr 127.0.0.1 meta skuid "$USER" accept
    ip6 daddr ::1 meta skuid "$USER" accept
    #
    # Anthropic addresses https://docs.anthropic.com/en/api/ip-addresses
    ip daddr 160.79.104.0/23 meta skuid "$USER" accept
    ip6 daddr 2607:6bc0::/48 meta skuid "$USER" accept

    # Drop all other traffic from the group
    meta skuid "$USER" drop
  }
}
EOF
)

# 3. Apply if different from current
nft delete table inet "$TABLE" 2>/dev/null || true
echo "$NFT_RULESET" | nft -f -
