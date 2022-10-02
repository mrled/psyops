"""The command line interface for progfiguration"""

import argparse
import importlib
import logging
import os
import pdb
import sys
from typing import List, Union

from progfiguration import age, progfiguration_build_path, version
from progfiguration.cli import (
    broken_pipe_handler,
    configure_logging,
    idb_excepthook,
    progfiguration_log_levels,
    syslog_excepthook,
)
from progfiguration.inventory import inventory
from progfiguration.inventory.groups import universal
from progfiguration.localhost import LocalhostLinuxPsyopsOs


def ResolvedPath(p: str) -> str:
    """Convert a user-input path to an absolute path"""
    return os.path.realpath(os.path.normpath(os.path.expanduser(p)))


def nodename2mod(nodename: str):
    nodemod = importlib.import_module(f"progfiguration.inventory.nodes.{nodename}")
    return nodemod


def groupname2mod(groupname: str):
    gmod = importlib.import_module(f"progfiguration.inventory.groups.{groupname}")
    return gmod


def rolename2mod(rolename: str):
    rolemodule = importlib.import_module(f"progfiguration.roles.{rolename}")
    return rolemodule


def action_apply(nodename: str, strace_before_applying: bool = False):
    """Apply configuration for the node 'nodename' to localhost"""

    node = nodename2mod(nodename).node

    # TODO: call this something else
    nodectx = LocalhostLinuxPsyopsOs(nodename)

    groupmods = {
        "universal": universal,
    }
    for groupname in inventory.node_groups[nodename]:
        groupmods[groupname] = groupname2mod(groupname)

    applyroles = {}
    for rolename in inventory.node_roles(nodename):
        rolemodule = rolename2mod(rolename)

        # If the role module itself has defaults, set them
        rolevars = {}
        if hasattr(rolemodule, "defaults"):
            rolevars.update(rolemodule.defaults)

        # The role module may define some values as "appends",
        # which means that they cannot be overridden by groups/nodes, only appended to.
        appendvars = []
        if hasattr(rolemodule, "appends"):
            appendvars = rolemodule.appends
            for append in appendvars:
                if append not in rolevars:
                    rolevars[append] = []

        # Check each group that the node is in for role arguments
        for gmod in groupmods.values():
            group_rolevars = getattr(gmod.group.roles, rolename, {})
            for key, value in group_rolevars.items():
                if key in appendvars:
                    rolevars[key].append(value)
                else:
                    rolevars[key] = value

        # Apply any role arguments from the node itself
        node_rolevars = getattr(node.roles, rolename, {})
        for key, value in node_rolevars.items():
            if key in appendvars:
                rolevars[key].append(value)
            else:
                rolevars[key] = value

        # Secret values are encrypted values where the key name is preceded by `secret_`
        # Find these and decrypt them
        # TODO: This means a `secret_` value defined as a default will OVERRIDE a non `_secret` value defined more specifically. Fix this.
        decrypted_rolevars = {}
        for vname, vvalue in rolevars.items():
            if vname.startswith("secret_"):
                nonsecret_vname = vname[7:]
                if vname in appendvars or nonsecret_vname in appendvars:
                    raise Exception(
                        f"The var {nonsecret_vname} is an append-only variable, but at least one of the role, group, or node values for it is secret, which is not currently supported. TODO: support this."
                    )
                # TODO: don't hard code key path here
                decrypted_vvalue = age.decrypt(vvalue, "/mnt/psyops-secret/mount/age.key")
                decrypted_rolevars[nonsecret_vname] = decrypted_vvalue
            else:
                decrypted_rolevars[vname] = vvalue

        applyroles[rolename] = (rolemodule, decrypted_rolevars)

    if strace_before_applying:
        pdb.set_trace()
    else:
        for rolename, role in applyroles.items():
            rolemodule, decrypted_rolevars = role
            logging.debug(f"Running role {rolename}...")
            rolemodule.apply(nodectx, **decrypted_rolevars)
            logging.info(f"Finished running role {rolename}.")

    logging.info(f"Finished running all roles")


def action_list(collection: str):
    if collection == "nodes":
        for node in inventory.nodes:
            print(node)
    elif collection == "groups":
        for group in inventory.groups:
            print(group)
    elif collection == "functions":
        for function in inventory.functions:
            print(function)
    else:
        raise Exception(f"Unknown collection {collection}")


def action_info(nodes: List[str], groups: List[str], functions: List[str]):
    if not any([nodes, groups, functions]):
        print("Request info on a node, group, or function. (See also the 'list' subcommand.)")
    for nodename in nodes:
        node_groups = inventory.node_groups[nodename]
        node_group_commas = ", ".join(node_groups)
        node_function = inventory.node_function[nodename]
        node_roles = inventory.function_roles[node_function]
        node_roles_commas = ", ".join(node_roles)
        print(f"Node {nodename} (function {node_function}):")
        print(f"  Groups: {node_group_commas}")
        print(f"  Roles: {node_roles_commas}")
    for groupname in groups:
        group_members = inventory.group_members[groupname]
        group_members_commas = ", ".join(group_members)
        print(f"Group {groupname}:")
        print(f"  Members: {group_members_commas}")
    for funcname in functions:
        function_nodes = ", ".join(inventory.function_nodes[funcname])
        function_roles = ", ".join(inventory.function_roles[funcname])
        print(f"Function {funcname}:")
        print(f"  Nodes: {function_nodes}")
        print(f"  Roles: {function_roles}")


def action_encrypt(value: str, nodes: List[str], groups: List[str], functions: List[str]):
    for group in groups:
        nodes += inventory.group_members[group]
    for function in functions:
        nodes += inventory.function_nodes[function]
    nodes = set(nodes)
    nmods = [nodename2mod(n) for n in nodes]
    pubkeys = [nm.node.pubkey for nm in nmods]

    print("Encrypting for all of these recipients:")
    for pk in pubkeys:
        print(pk)

    print(age.encrypt(value, pubkeys).decode())


def action_build_action_apk(apkdir: str):

    # Get the module by path
    spec = importlib.util.spec_from_file_location("progfiguration_build", progfiguration_build_path)
    progfiguration_build = importlib.util.module_from_spec(spec)
    sys.modules["progfiguration_build"] = progfiguration_build
    spec.loader.exec_module(progfiguration_build)

    # Run the build
    progfiguration_build.build_alpine(apkdir)


def action_build_action_save_version(version: Union[str, None]):

    # Get the module by path
    spec = importlib.util.spec_from_file_location("progfiguration_build", progfiguration_build_path)
    progfiguration_build = importlib.util.module_from_spec(spec)
    sys.modules["progfiguration_build"] = progfiguration_build
    spec.loader.exec_module(progfiguration_build)

    # Save the version
    if not version:
        version = progfiguration_build.get_epoch_build_version()
    progfiguration_build.set_build_version(version)
    print("Saved APKBUILD and package version files:")
    print(progfiguration_build.APKBUILD_FILE)
    print(progfiguration_build.PKG_VERSION_FILE)
    print("Take care not to commit these files to git")


def parseargs(arguments: List[str]):
    parser = argparse.ArgumentParser("psyopsOS programmatic configuration")

    group_onerr = parser.add_mutually_exclusive_group()
    group_onerr.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Open the debugger if an unhandled exception is encountered",
    )
    group_onerr.add_argument(
        "--syslog-exception",
        action="store_true",
        help="When encountering an unhandle exception, print exception details to syslog before exiting",
    )

    parser.add_argument(
        "--log-stderr",
        default="NOTSET",
        choices=progfiguration_log_levels,
        help="Log level to send to stderr. Defaults to NOTSET (all messages, including debug). NONE to disable.",
    )
    parser.add_argument(
        "--log-syslog",
        default="INFO",
        choices=progfiguration_log_levels,
        help="Log level to send to syslog. Defaults to INFO. NONE to disable.",
    )

    subparsers = parser.add_subparsers(dest="action", required=True)

    svn = subparsers.add_parser("version", description="Show progfiguration version")

    sub_apply = subparsers.add_parser("apply", description="Apply configuration")
    sub_apply.add_argument("nodename", help="The name of a node in the progfiguration inventory")
    sub_apply.add_argument(
        "--strace-before-applying",
        action="store_true",
        help="Do not actually apply the role. Instead, launch a debugger. Intended for development.",
    )

    sub_list = subparsers.add_parser("list", description="List inventory items")
    list_choices = ["nodes", "groups", "functions", "svcpreps"]
    sub_list.add_argument(
        "collection",
        choices=list_choices,
        help=f"The items to list. Options: {list_choices}",
    )

    sub_info = subparsers.add_parser("info", description="Display info about nodes and groups")
    sub_info.add_argument("--group", "-g", action="append", help="Show info for this group")
    sub_info.add_argument("--node", "-n", action="append", help="Show info for this node")
    sub_info.add_argument("--function", "-f", action="append", help="Show info for this function")

    sub_encrypt = subparsers.add_parser("encrypt", description="Encrypt a value with age")
    sub_encrypt.add_argument("value", help="Encrypt this value")
    sub_encrypt.add_argument("--group", "-g", action="append", help="Encrypt for every node in this group")
    sub_encrypt.add_argument("--node", "-n", action="append", help="Encrypt for this node")
    sub_encrypt.add_argument("--function", "-f", action="append", help="Encrypt for this function")

    sub_build = subparsers.add_parser("build", description="Build the package")
    sub_build_subparsers = sub_build.add_subparsers(dest="buildaction", required=True)
    sub_build_sub_apk = sub_build_subparsers.add_parser(
        "apk",
        description="Build an Alpine APK package. Must be run from an editable install on an Alpine linux system with the appropriate signing keys.",
    )
    sub_build_sub_apk.add_argument("apkdir", type=ResolvedPath, help="Save the resulting package to this directory")
    sub_build_sub_version = sub_build_subparsers.add_parser(
        "save-version", description="Save the Python module and APKBUILD file with a version number"
    )
    sub_build_sub_version.add_argument(
        "--version", help="Set the version to this string. If not present, use a version based on the epoch."
    )

    parsed = parser.parse_args(arguments)
    return parsed


def main(*arguments):
    parsed = parseargs(arguments[1:])

    if parsed.debug:
        sys.excepthook = idb_excepthook
    elif parsed.syslog_exception:
        sys.excepthook = syslog_excepthook
    configure_logging(parsed.log_stderr, parsed.log_syslog)

    if parsed.action == "version":
        print(version.getversion())
    elif parsed.action == "apply":
        action_apply(parsed.nodename, strace_before_applying=parsed.strace_before_applying)
    elif parsed.action == "list":
        action_list(parsed.collection)
    elif parsed.action == "info":
        action_info(parsed.node or [], parsed.group or [], parsed.function or [])
    elif parsed.action == "encrypt":
        action_encrypt(parsed.value, parsed.node or [], parsed.group or [], parsed.function or [])

    elif parsed.action == "build":
        if parsed.buildaction == "apk":
            action_build_action_apk(parsed.apkdir)
        elif parsed.buildaction == "save-version":
            action_build_action_save_version(parsed.version)
        else:
            raise Exception(f"Unknown build action {parsed.buildaction}")
    else:
        raise Exception(f"Unknown action {parsed.action}")


def wrapped_main():
    broken_pipe_handler(main, *sys.argv)
