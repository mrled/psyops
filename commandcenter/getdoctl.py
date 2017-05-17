#!/usr/bin/env python3
import json, os, re, urllib.request
latesturi = 'https://api.github.com/repos/digitalocean/doctl/releases/latest'
scriptdir = os.path.dirname(os.path.realpath(__file__))
jbody = json.loads(urllib.request.urlopen(latesturi).read().decode())
assets = [asset for asset in jbody['assets'] if re.search('^doctl.*linux.*amd64.*', asset['name'])]
for ass in assets:
    if re.search('^doctl.*linux.*amd64.*', ass['name']):
        with open('{}/{}'.format(scriptdir, ass['name']), 'wb') as afile:
            afile.write(urllib.request.urlopen(ass['browser_download_url']).read())
