# xmpp_server

Standalone Ansible role to install and configure a Prosody XMPP server.

```bash
# Create admin user (not created by default)
prosodyctl adduser admin@example.com

# Create other users
prosodyctl adduser username@example.com

# Check status
prosodyctl status
systemctl status prosody

# View logs
tail -f /var/log/prosody/prosody.log

# Check DNS
prosodyctl check dns xmpp.micahrl.com
dig xmpp.micahrl.com
dig SRV _xmpp-client._tcp.micahrl.com
dig SRV _xmpp-server._tcp.micahrl.com
```
