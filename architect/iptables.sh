#!/bin/sh

# REMINDER: DROP vs REJECT:
# a DROP operation blackholes the packet, likely causing client to wait dozens of seconds for a timeout
# a REJECT operation sends an ICMP response letting the client know the packet was rejected

for ipaddr in $(ip -family inet -o address show dev eth0 | awk '!/^[0-9]*: ?lo|link\/ether/ {print $4}'); do
    # Allow established sessions to receive traffic
    iptables --append INPUT --destination "$ipaddr" --match conntrack --ctstate ESTABLISHED,RELATED --jump ACCEPT
    # Allow SSH
    iptables --append INPUT --destination "$ipaddr" --protocol tcp --dport 22 --jump ACCEPT
    # Allow incoming UDP 9993 on eth0 (required for ZeroTier)
    iptables --append INPUT --destination "$ipaddr" --protocol udp --dport 9993 --jump ACCEPT
    # Reject everything that hasn't already been accepted (rules are applied in order)
    iptables --append INPUT --destination "$ipaddr" --jump REJECT
done

# Allow established sessions to receive traffic
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow SSH on eth0
iptables -A INPUT -i eth0 -p tcp --dport 22 -j ACCEPT

# Allow UDP 9993 on eth0 (required for ZeroTier)
iptables -A INPUT -i eth0 -p udp --dport 9993 -j ACCEPT
iptables -A OUTPUT -p udp --dport 9993 -j ACCEPT

# Reject everything that hasn't already been accepted (rules are applied in order)
iptables -A INPUT -i eth0 -j REJECT


# Do not allow FORWARD packets on eth0 under any circumstances
# iptables -A FORWARD -i eth0 -j REJECT
# ip6tables -A FORWARD -i eth0 -j REJECT



ip6tables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
ip6tables -A INPUT -i eth0 -p tcp --dport 22 -j ACCEPT
ip6tables -A INPUT -i eth0 -p udp --dport 9993 -j ACCEPT
ip6tables -A OUTPUT -p udp --dport 9993 -j ACCEPT
ip6tables -A INPUT -i eth0 -j REJECT
