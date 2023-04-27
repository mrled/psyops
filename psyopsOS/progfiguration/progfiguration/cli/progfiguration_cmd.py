"""The command line interface for progfiguration"""

import argparse
import importlib
import logging
import os
import pathlib
import pdb
import subprocess
import sys
import tempfile
import time
from typing import List, Union

from progfiguration import logger, progfiguration_build_path, remotebrute, site, version
from progfiguration.cli import (
    progfiguration_error_handler,
    configure_logging,
    idb_excepthook,
    progfiguration_log_levels,
    syslog_excepthook,
    yaml_dump_str,
)
from progfiguration.inventory import Inventory

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


def import_progfiguration_build():
    """Import the progfiguration_build module

    This module is also used outside of the progfiguration CLI, which is why we do this.
    """
    spec = importlib.util.spec_from_file_location("progfiguration_build", progfiguration_build_path)
    progfiguration_build = importlib.util.module_from_spec(spec)
    sys.modules["progfiguration_build"] = progfiguration_build
    spec.loader.exec_module(progfiguration_build)
    return progfiguration_build


def action_apply(inventory: Inventory, nodename: str, roles: list[str] = None, force: bool = False):
    """Apply configuration for the node 'nodename' to localhost"""

    if roles is None:
        roles = []

    node = inventory.node(nodename).node

    if node.TESTING_DO_NOT_APPLY and not force:
        raise Exception(
            f"Was going to apply progfiguration to node {nodename} but TESTING_DO_NOT_APPLY is True for that node."
        )

    for role in inventory.node_role_list(nodename):
        if not roles or role.name in roles:
            try:
                logging.debug(f"Running role {role.name}...")
                role.apply()
                logging.info(f"Finished running role {role.name}.")
            except Exception as exc:
                logging.error(f"Error running role {role.name}: {exc}")
                raise
        else:
            logging.info(f"Skipping role {role.name}.")

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


def action_build(parsed: argparse.Namespace):
    """Build the progfiguration package

    Must pass in the parsed arguments from the main command.
    """

    progfiguration_build = import_progfiguration_build()

    if parsed.buildaction == "apk":
        progfiguration_build.build_alpine(parsed.apkdir)
    elif parsed.buildaction == "pyz":
        progfiguration_build.build_zipapp(parsed.pyzfile)
    elif parsed.buildaction == "save-version":
        if not version:
            version = progfiguration_build.get_epoch_build_version()
        progfiguration_build.set_build_version(version)
        print("Saved APKBUILD and package version files:")
        print(progfiguration_build.APKBUILD_FILE)
        print(progfiguration_build.PKG_VERSION_FILE)
        print("Take care not to commit these files to git")
    else:
        raise Exception(f"Unknown buildaction {parsed.buildaction}")


def action_rcmd(inventory: Inventory, nodes: List[str], groups: List[str], cmd: str):
    remoting.command(inventory, nodes, groups, cmd)


def action_deploy_apply(
    inventory: Inventory,
    nodenames: List[str],
    groupnames: List[str],
    roles: List[str],
    remote_debug: bool,
    force_apply: bool,
    keep_remote_file: bool,
):

    if roles is None:
        roles = []

    progfiguration_build = import_progfiguration_build()

    nodenames = set(nodenames + [inventory.group_members(g) for g in groupnames])
    nodes = {n: inventory.node(n).node for n in nodenames}

    errors: list[dict[str, str]] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        pyzfile = os.path.join(tmpdir, "progfiguration.pyz")
        progfiguration_build.build_zipapp(pyzfile)
        for nname, node in nodes.items():
            args = []
            if remote_debug:
                args.append("--debug")
            args += ["apply", nname]
            if force_apply:
                args.append("--force-apply")
            if roles:
                args += ["--roles", ",".join(roles)]

            # To run progfiguration remotely over ssh, we need:
            # * To run Python unbuffered with -u
            # * To ask sshd to create a tty with -tt
            # * To redirect stdin to /dev/null,
            #   which fixes some weird issues with bad newlines in the output for reasons I don't understand.
            # The result isn't perfect, as some lines are not printed exactly as they were in the output, but it's ok.
            try:
                remotebrute.cpexec(
                    f"{node.user}@{node.address}",
                    pyzfile,
                    args,
                    interpreter=["python3", "-u"],
                    ssh_tty=True,
                    ssh_stdin=subprocess.DEVNULL,
                    keep_remote_file=keep_remote_file,
                )
            # except subprocess.CalledProcessError as exc:
            except Exception as exc:
                print(f"Error running progfiguration on node {nname}:")
                logger.debug(exc)
                errors.append({"node": nname, "error": str(exc)})

    if errors:
        print("====================")
        print("Errors running progfiguration on {len(errors)} node(s):")
        for error in errors:
            print(f"  {error['node']}: {error['error']}")


def action_deploy_copy(
    inventory: Inventory,
    nodenames: List[str],
    groupnames: List[str],
    remotepath: str,
):
    progfiguration_build = import_progfiguration_build()

    nodenames = set(nodenames + [inventory.group_members(g) for g in groupnames])
    nodes = {n: inventory.node(n).node for n in nodenames}

    with tempfile.TemporaryDirectory() as tmpdir:
        pyzfile = os.path.join(tmpdir, "progfiguration.pyz")
        progfiguration_build.build_zipapp(pyzfile)
        for nname, node in nodes.items():
            remotebrute.scp(f"{node.user}@{node.address}", pyzfile, remotepath)


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

    def syslog_default():
        if os.path.exists("/dev/log"):
            return "INFO"
        return "NONE"

    parser.add_argument(
        "--log-syslog",
        default=syslog_default(),
        choices=progfiguration_log_levels,
        help="Log level to send to syslog. Defaults to INFO if /dev/log exists, otherwise NONE. NONE to disable. If a value other than NONE is passed explicitly and /dev/log does not exist, an exception will be raised.",
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
        default=site.package_inventory_file,
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

    # --roles option
    roles_opts = argparse.ArgumentParser(add_help=False)
    roles_opts.add_argument(
        "--roles",
        "-r",
        default=[],
        type=CommaSeparatedStrList,
        help="A role, or list of roles separated by commas. The role(s) must be defined in the inventory for the node(s).",
    )

    subparsers = parser.add_subparsers(dest="action", required=True)

    # version subcommand
    svn = subparsers.add_parser("version", description="Show progfiguration version")

    # apply subcommand
    sub_apply = subparsers.add_parser("apply", parents=[roles_opts], description="Apply configuration")
    sub_apply.add_argument("nodename", help="The name of a node in the progfiguration inventory")
    sub_apply.add_argument(
        "--force-apply", action="store_true", help="Force apply, even if the node has TESTING_DO_NOT_APPLY set."
    )

    # deploy subcommand
    sub_deploy = subparsers.add_parser(
        "deploy",
        parents=[node_opts],
        description="Deploy progfiguration to remote system in inventory as a pyz package (NOT a pip or apk package!); requires passwordless SSH configured",
    )
    sub_deploy_subparsers = sub_deploy.add_subparsers(dest="deploy_action", required=True)
    sub_deploy_sub_apply = sub_deploy_subparsers.add_parser(
        "apply", parents=[roles_opts], description="Deploy and apply configuration"
    )
    sub_deploy_sub_apply.add_argument(
        "--remote-debug",
        action="store_true",
        help="Open the debugger on the remote system if an unhandled exception is encountered",
    )
    sub_deploy_sub_apply.add_argument(
        "--force-apply", action="store_true", help="Force apply, even if the node has TESTING_DO_NOT_APPLY set."
    )
    sub_deploy_sub_apply.add_argument(
        "--keep-remote-file", action="store_true", help="Don't delete the remote file after execution"
    )
    sub_deploy_sub_copy = sub_deploy_subparsers.add_parser(
        "copy", description="Copy the configuration to the remote system"
    )
    default_dest = f"/tmp/progfiguration-{str(time.time()).replace('.', '')}.pyz"
    sub_deploy_sub_copy.add_argument(
        "--destination",
        "-d",
        default=default_dest,
        help=f"The destination path on the remote system, default is based on the time this program was started, like {default_dest}",
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
    sub_build_sub_pyz = sub_build_subparsers.add_parser(
        "pyz",
        description="Build a zipapp .pyz file containing the Python module. Must be run from an editable install.",
    )
    sub_build_sub_pyz.add_argument("pyzfile", type=ResolvedPath, help="Save the resulting pyz file to this path")
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

    # debugger subcommand
    sub_debugger = subparsers.add_parser(
        "debugger",
        description="Open a debugger on localhost.",
    )

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

    inventory_file = parsed.inventory_file
    if not hasattr(inventory_file, "open"):
        inventory_file = pathlib.Path(inventory_file)
    inventory = Inventory(parsed.inventory_file, parsed.age_private_key)

    if parsed.action == "version":
        print(version.VersionInfo.from_build_version_or_default().verbose())
    elif parsed.action == "apply":
        action_apply(inventory, parsed.nodename, roles=parsed.roles, force=parsed.force_apply)
    elif parsed.action == "deploy":
        if not parsed.nodes and not parsed.groups:
            parser.error("You must pass at least one of --nodes or --groups")
        if parsed.deploy_action == "apply":
            action_deploy_apply(
                inventory,
                parsed.nodes,
                parsed.groups,
                roles=parsed.roles,
                remote_debug=parsed.remote_debug,
                force_apply=parsed.force_apply,
                keep_remote_file=parsed.keep_remote_file,
            )
        elif parsed.deploy_action == "copy":
            action_deploy_copy(inventory, parsed.nodes, parsed.groups, parsed.destination)
            print(f"Copied to remote host(s) at {parsed.destination}")
        else:
            raise ValueError(f"Unknown deploy action {parsed.deploy_action}")
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
        action_rcmd(inventory, parsed.nodes, parsed.groups, parsed.command)
        # remoting.mitogen_example()
    elif parsed.action == "build":
        action_build(parsed)
    elif parsed.action == "debugger":
        pdb.set_trace()
    else:
        raise Exception(f"Unknown action {parsed.action}")


def main():
    progfiguration_error_handler(main_implementation, *sys.argv)
