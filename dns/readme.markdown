# micahrl.com DNS

I use the Gandi client.

Install:

    python -m pip install gandi.cli

Configure:

    gandi setup

Get the current zonefile:

    # Unix
    gandi record list --format text DOMAIN > DOMAIN.zone

    # Powerhell
    gandi record list --format text DOMAIN > Out-File -Encoding utf8 -FilePath DOMAIN.zone

Deploy a new zonefile:

    gandi record update DOMAIN -f DOMAIN.zone
