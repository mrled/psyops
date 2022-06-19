"""My home k3s cluster"""

from progfiguration.inventory.invhelpers import Bunch


# Randomly generated token with
# cat /dev/urandom | LC_ALL=C tr -dc 'a-zA-Z0-9' | fold -w 50 | head -n 1
kubernasty_k3s_server_token = """\
-----BEGIN AGE ENCRYPTED FILE-----
YWdlLWVuY3J5cHRpb24ub3JnL3YxCi0+IFgyNTUxOSBGbUxNUHlKNlVEaGRlNUtm
YjBSam5NeFBMODFLbE9EYlR4UlUrZndzUVE0CmNjM2ZYRFNIcVBJNFRwRXJBMUg4
RXlkWGVGWEVNL0Noeis0dUNYZllxQjgKLT4gWDI1NTE5IEhQWTVhY1NQSktOT3Yx
aXFhWmlIMFpOUzdyNTBPV0Y5aXllYVljTkRTak0KR1BNTGlSVFo4TjhRRzIxT3hM
TjJWeXBNUmtkUXBoSTNqSXVLUXluNERMSQotPiBYMjU1MTkgS20yb0FPZlYrZHhM
RGVlazhsbmtDZjc5alZKemY4WC9XS2JVejJrNUtpSQpMRzBUY05rLzBvbmR2MUhY
TkJkQjdiQW1odXgvYmY1RFVGeWUzREp3cDlZCi0+IFgyNTUxOSB4TVVRN210NGw0
dUZ3TmdwYmdrOGQ0a2Z5WmxJT3MxTSt1Qjg3TTI2QmxnCjJIbGt6SFRPTkpIVWFy
bnpsb3VabElhWGh4MWdiRnpPWTVuSnBteUJ5TlUKLS0tIE1TUXpGM3V6dWtZY3I1
cy9qRnVaSXRueHdOTnphQ3VnUmp1cWJpWUZpYkkKhnrjwwSaejCXXYE6y0WyPxqc
+aJ0wc8SM79jSK7wvrxavjcSQX7Jo4dFXXVsoA2E6oVerGCs0EWDNrgdxs1VxfE6
PPhUGmZLadFuc2ngjbYP1A==
-----END AGE ENCRYPTED FILE-----
"""


node = Bunch(
    roles = Bunch(
        datadisk = {},
        k3s = {
            'secret_server_token': kubernasty_k3s_server_token,
        },
    ),
)
