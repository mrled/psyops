#!/usr/bin/python3


import typing


def dnsname2x500domaincomponents(dnsname: typing.AnyStr) -> str:
    """Given a dnsname like asdf.example.com, return a string with x.500 Domain Components like DC=asdf,DC=example,DC=com"""
    if not isinstance(dnsname, str):
        dnsname = dnsname.decode()
    split = dnsname.split(".")
    components_list = [f"DC={c}" for c in split]
    components = ",".join(components_list)
    return components


class FilterModule(object):
    def filters(self):
        return {
            "dnsname2x500domaincomponents": dnsname2x500domaincomponents,
        }
