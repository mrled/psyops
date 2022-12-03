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
from progfiguration.inventory import Inventory, package_inventory_file
from progfiguration.localhost import LocalhostLinuxPsyopsOs
from progfiguration.roles.util import yaml_dump_str

try:
    from progfiguration import remoting

    REMOTING = True
except ModuleNotFoundError:
    REMOTING = False


def ResolvedPath(p: str) -> str:
    """Convert a user-input path to an absolute path"""
    return os.path.realpath(os.path.normpath(os.path.expanduser(p)))


def CommaSeparatedStrList(cssl: str) -> List[str]:
    """Convert a string with commas into a list of strings"""
    return cssl.split(",")


def action_apply(inventory: Inventory, nodename: str, strace_before_applying: bool = False):
    """Apply configuration for the node 'nodename' to localhost"""

    node = inventory.node(nodename).node

    localhost = LocalhostLinuxPsyopsOs(nodename)

    groupmods = {}
    for groupname in inventory.node_groups[nodename]:
        groupmods[groupname] = inventory.group(groupname)

    applyroles = {}
    for rolename in inventory.node_roles(nodename):
        rolemodule = inventory.role(rolename)

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
                unencrypted_value = value
                if isinstance(value, age.AgeSecretReference):
                    secret = inventory.get_group_secrets(key)[value.name]
                    unencrypted_value = secret.decrypt()
                if key in appendvars:
                    rolevars[key].append(unencrypted_value)
                else:
                    rolevars[key] = unencrypted_value

        # Apply any role arguments from the node itself
        node_rolevars = getattr(node.roles, rolename, {})
        for key, value in node_rolevars.items():
            unencrypted_value = value
            if isinstance(value, age.AgeSecretReference):
                secret = inventory.get_node_secrets(key)[value.name]
                unencrypted_value = secret.decrypt()
            if key in appendvars:
                rolevars[key].append(unencrypted_value)
            else:
                rolevars[key] = unencrypted_value

        applyroles[rolename] = (rolemodule, rolevars)

    if strace_before_applying:
        pdb.set_trace()
    else:
        for rolename, role in applyroles.items():
            rolemodule, rolevars = role
            logging.debug(f"Running role {rolename}...")
            rolemodule.apply(localhost, **rolevars)
            logging.info(f"Finished running role {rolename}.")

    logging.info(f"Finished running all roles")


def action_list(inventory: Inventory, collection: str):
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


def action_info(inventory: Inventory, nodes: List[str], groups: List[str], functions: List[str]):
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


def action_encrypt(
    inventory: Inventory,
    name: str,
    value: str,
    nodes: List[str],
    groups: List[str],
    controller_key: bool,
    store: bool,
    stdout: bool,
):
    encrypted_value, recipients = inventory.encrypt_secret(name, value, nodes, groups, controller_key, store=store)
    print("Encrypted for all of these recipients:")
    for pk in recipients:
        print(pk)
    if stdout:
        print(encrypted_value)


def action_decrypt(inventory: Inventory, nodes: List[str], groups: List[str], controller_key: bool):
    for node in nodes:
        print(f"Secrets for node {node}:")
        print("---")
        decrypted_secrets = {k: v.decrypt(inventory.age_path) for k, v in inventory.get_node_secrets(node).items()}
        print(yaml_dump_str(decrypted_secrets, {"default_style": "|"}))
        print("---")
    for group in groups:
        print(f"Secrets for group {group}:")
        print("---")
        decrypted_secrets = {k: v.decrypt(inventory.age_path) for k, v in inventory.get_group_secrets(group).items()}
        print(yaml_dump_str(decrypted_secrets, {"default_style": "|"}))
        print("---")
    if controller_key:
        print(f"Secrets for the controller:")
        print("---")
        decrypted_secrets = {k: v.decrypt(inventory.age_path) for k, v in inventory.get_controller_secrets().items()}
        print(yaml_dump_str(decrypted_secrets, {"default_style": "|"}))
        print("---")


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


def action_rcmd(inventory: Inventory, nodes: List[str], groups: List[str], cmd: str):
    remoting.command(inventory, nodes, groups, cmd)


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
    parser.add_argument(
        "--mitogen-log-stderr",
        default="CRITICAL",
        choices=progfiguration_log_levels,
        help="Log level for mitogen messages to stderr. Only used for remote commands from the controller.",
    )
    parser.add_argument(
        "--mitogen-io-log-stderr",
        default="CRITICAL",
        choices=progfiguration_log_levels,
        help="Log level for mitogen IO messages to stderr. Only used for remote commands from the controller.",
    )
    parser.add_argument(
        "--inventory-file",
        "-f",
        default=package_inventory_file,
        help="The path to an inventory yaml file. By default, use the one in the package",
    )
    parser.add_argument(
        "--age-private-key", "-k", help="The path to an age private key that decrypts inventory secrets"
    )

    # node/group related options
    node_opts = argparse.ArgumentParser(add_help=False)
    node_opts.add_argument(
        "--nodes", "-n", default=[], type=CommaSeparatedStrList, help="A node, or list of nodes separated by commas"
    )
    node_opts.add_argument(
        "--groups", "-g", default=[], type=CommaSeparatedStrList, help="A group, or list of groups separated by commas"
    )

    # function related options
    func_opts = argparse.ArgumentParser(add_help=False)
    func_opts.add_argument(
        "--functions",
        "-f",
        default=[],
        type=CommaSeparatedStrList,
        help="A function, or list of functions separated by commas",
    )

    # --controller option
    # TODO: document that everything is always encrypted for the controller
    ctrl_opts = argparse.ArgumentParser(add_help=False)
    ctrl_opts.add_argument(
        "--controller", "-c", action="store_true", help="En/decrypt to/from the controller secret store"
    )

    subparsers = parser.add_subparsers(dest="action", required=True)

    # version subcommand
    svn = subparsers.add_parser("version", description="Show progfiguration version")

    # apply subcommand
    sub_apply = subparsers.add_parser("apply", description="Apply configuration")
    sub_apply.add_argument("nodename", help="The name of a node in the progfiguration inventory")
    sub_apply.add_argument(
        "--strace-before-applying",
        action="store_true",
        help="Do not actually apply the role. Instead, launch a debugger. Intended for development.",
    )

    # list subcommand
    sub_list = subparsers.add_parser("list", description="List inventory items")
    list_choices = ["nodes", "groups", "functions", "svcpreps"]
    sub_list.add_argument(
        "collection",
        choices=list_choices,
        help=f"The items to list. Options: {list_choices}",
    )

    # info subcommand
    sub_info = subparsers.add_parser(
        "info", parents=[node_opts, func_opts], description="Display info about nodes and groups"
    )

    # encrypt subcommand
    sub_encrypt = subparsers.add_parser(
        "encrypt", parents=[node_opts, ctrl_opts], description="Encrypt a value with age"
    )
    sub_encrypt_value_group = sub_encrypt.add_mutually_exclusive_group()
    sub_encrypt_value_group.add_argument("--value", help="Encrypt this value")
    sub_encrypt_value_group.add_argument("--file", help="Encrypt the contents of this file")
    sub_encrypt.add_argument(
        "--save-as",
        help="Save under this name in each node/group's secret store. Otherwise, just print to stdout and do not save.",
    )
    sub_encrypt.add_argument("--stdout", action="store_true", help="Print encrypted value to stdout")

    # decrypt subcommand
    sub_decrypt = subparsers.add_parser(
        "decrypt", parents=[node_opts, ctrl_opts], description="Decrypt secrets from the secret store"
    )

    # build subcommand
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

    # rcmd subcommand
    sub_rcmd = subparsers.add_parser(
        "rcmd",
        parents=[node_opts],
        description="Run a command on remote nodes. Intended to be run from the controller.",
    )
    sub_rcmd.add_argument(
        "--sh", action="store_true", help="Run the command inside a shell, rather than directly on the host"
    )
    sub_rcmd.add_argument("command", help="A command to run remotely")

    # Parse and return
    parsed = parser.parse_args(arguments)
    return parser, parsed


def main_implementation(*arguments):
    parser, parsed = parseargs(arguments[1:])

    if parsed.debug:
        sys.excepthook = idb_excepthook
    elif parsed.syslog_exception:
        sys.excepthook = syslog_excepthook
    configure_logging(parsed.log_stderr, parsed.log_syslog)

    if REMOTING:
        mitogen_core_level = logging._nameToLevel[parsed.mitogen_log_stderr]
        mitogen_io_level = logging._nameToLevel[parsed.mitogen_io_log_stderr]
        remoting.configure_mitogen_logging(mitogen_core_level, mitogen_io_level)

    inventory = Inventory(parsed.inventory_file, parsed.age_private_key)

    if parsed.action == "version":
        print(version.getversion())
    elif parsed.action == "apply":
        action_apply(inventory, parsed.nodename, strace_before_applying=parsed.strace_before_applying)
    elif parsed.action == "list":
        action_list(inventory, parsed.collection)
    elif parsed.action == "info":
        action_info(inventory, parsed.nodes, parsed.groups, parsed.functions)
    elif parsed.action == "encrypt":
        if not parsed.nodes and not parsed.groups and not parsed.controller:
            parser.error("You must pass at least one of --nodes, --groups, or --controller")
        if not parsed.value and not parsed.file:
            parser.error("You must pass one of --value or --file")
        if parsed.file:
            with open(parsed.file) as fp:
                value = fp.read()
        else:
            value = parsed.value
        action_encrypt(
            inventory,
            parsed.save_as or "",
            value,
            parsed.nodes,
            parsed.groups,
            parsed.controller,
            bool(parsed.save_as),
            parsed.stdout,
        )
    elif parsed.action == "decrypt":
        if not parsed.nodes and not parsed.groups and not parsed.controller:
            parser.error("You must pass at least one of --nodes, --groups, or --controller")
        action_decrypt(inventory, parsed.nodes, parsed.groups, parsed.controller)
    elif parsed.action == "rcmd":
        if not REMOTING:
            raise Exception("Could not import remoting module - make sure mitogen is installed")
        if not parsed.nodes and not parsed.groups:
            parser.error("You must pass at least one of --nodes or --groups")
        # action_rcmd(inventory, parsed.nodes, parsed.groups, parsed.command)
        remoting.mitogen_example()
    elif parsed.action == "build":
        if parsed.buildaction == "apk":
            action_build_action_apk(parsed.apkdir)
        elif parsed.buildaction == "save-version":
            action_build_action_save_version(parsed.version)
        else:
            raise Exception(f"Unknown build action {parsed.buildaction}")
    else:
        raise Exception(f"Unknown action {parsed.action}")


def main():
    broken_pipe_handler(main_implementation, *sys.argv)
