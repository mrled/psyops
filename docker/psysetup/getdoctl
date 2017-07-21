#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
import urllib.request


latesturi = 'https://api.github.com/repos/digitalocean/doctl/releases/latest'


def main(*args, **kwargs):
    parser = argparse.ArgumentParser(
        description="Download the latest release of the doctl cli tool")
    parser.add_argument(
        "--outdir", "-o", default=os.getcwd(),
        help="Directory to save output file to. Defaults to PWD.")
    parsed = parser.parse_args()

    outdir = parsed.outdir

    jbody = json.loads(urllib.request.urlopen(latesturi).read().decode())
    assets = [asset for asset in jbody['assets'] if re.search('^doctl.*linux.*amd64.*', asset['name'])]
    for ass in assets:
        if re.search('^doctl.*linux.*amd64.*', ass['name']):
            with open('{}/{}'.format(outdir, ass['name']), 'wb') as afile:
                afile.write(urllib.request.urlopen(ass['browser_download_url']).read())


if __name__ == '__main__':
    sys.exit(main(*sys.argv))
