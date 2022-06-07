# To do

Outstanding items


## Add Chenoska startup tasks to ansible

* Task to fix Syncthing inotify thing: https://forum.syncthing.net/t/setting-inotify-limit-permanently-on-synology-diskstation/12221/4
* Task to call capthook to request the cert check

## Unify seedbox authentication

Currently, seedbox apps are all over the place for auth.
Can I bring them all together somehow?

The funkypenguin playbooks use oauth for this.
They're tired to GitHub - could I do my own instead?

## Back up seedbox configs

None of that stuff is backed up.
Under /etc/seedbox on tagasaw.

## Back up acmedns certificates

They're just stored under /etc/acmedns on kilotah.
Make a new backup_acmedns role that relies on backup_base like backup_unifi.

## Fix DNS in UniFi

* Currently, I have Unifi configured to use `whatever.homeward.micahrl.com.` for all clients.
* I also have `homeward.micahrl.com.` delegated to no-ip for dynamic DNS for remote access
* I'm using `home.micahrl.com.` as the canonical hostname for all machines defined in route53
* But reverse lookups go to the DNS forwarder in the USG, and return a `homeward.micahrl.com.` domain

Options:

* Enable dnsmasq in Unifi controller.
  Not sure if this would let me do CNAMEs, and I don't trust dnsmasq.
* DHCP relay instead of using DHCP server on the USG.
  Requires DHCP servers with ddns updates.
  I think local DNS like this is the only real option to fix reverse DNS lookups.
  (Could install FreeIPA for this; would need hardware and would be more to manage.)
* Use `home.micahrl.com.` in Unifi.
  Doesn't give me enough control. No CNAME support for example.

## Do automatic backup/restore

Especially for docker swarm services.

* If I have a backup and no local data, restore it
* Easy system for manual restores

## Cron times should be smarter

Currently hardcoding cron job times.
Should do something else, maybe?

## Do not host Matrix images on S3

This is V E R Y S L O W.

Also, this will let me remove the CloudFormation template for deploying the EC2 instance + S3 bucket, which I should do at some point because it's no longer in EC2, but in Digital Ocean now, and I just deployed the server initially by hand.

## Automatic updates of Matrix host

... or email reminders? Or something? Bleh.
