#!/bin/sh

set -e
set -u

# REMINDER: DROP vs REJECT:
# a DROP operation blackholes the packet, likely causing client to wait dozens of seconds for a timeout
# a REJECT operation sends an ICMP response letting the client know the packet was rejected

# REMINDER: IPv4 vs IPv6
# `iptables` only applies IPv4 rules; `ip6tables` only lapplies IPv6 rules.

## System firewall rules

# Allow any established sessions from our container host - including replies to outbound queries - to receive traffic
iptables --append INPUT -m conntrack --ctstate ESTABLISHED,RELATED --jump ACCEPT
ip6tables --append INPUT -m conntrack --ctstate ESTABLISHED,RELATED --jump ACCEPT

# Allow SSH on eth0
iptables --append INPUT --in-interface eth0 --protocol tcp --dport 22 --jump ACCEPT
ip6tables --append INPUT --in-interface eth0 --protocol tcp --dport 22 --jump ACCEPT

# Allow UDP 9993 on eth0 (required for ZeroTier)
iptables --append INPUT --in-interface eth0 --protocol udp --dport 9993 --jump ACCEPT
ip6tables --append INPUT --in-interface eth0 --protocol udp --dport 9993 --jump ACCEPT
iptables --append OUTPUT --protocol udp --dport 9993 --jump ACCEPT
ip6tables --append OUTPUT --protocol udp --dport 9993 --jump ACCEPT

# Reject everything to eth0 that hasn't been accepted by a previous rule
iptables --append INPUT --in-interface eth0 --jump REJECT
ip6tables --append INPUT --in-interface eth0 --jump REJECT

## Docker firewall rules

# NOTE: Docker does not enable IPv6 networking by default, so there is no need for `ip6tables` here
# <https://docs.docker.com/engine/userguide/networking/default_network/ipv6/>

# NOTE: Docker promises not to modify the DOCKER-USER chain so that we can do this type of filtering

# Create the chain we need if Docker hasn't done so already
iptables --new DOCKER-USER 2>/dev/null || true

# Allow any established sessions from our containers - including replies to outbound queries - to receive traffic
iptables --append DOCKER-USER --match conntrack --ctstate ESTABLISHED,RELATED --jump ACCEPT

# Reject packets that would be forwarded to Docker when they come in over eth0 (the public interface)
iptables --append DOCKER-USER --in-interface eth0 ---jump REJECT
