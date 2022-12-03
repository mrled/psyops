"""Remote connections for nodes in the inventory from the controller"""


import logging
import os
import socket
import subprocess
import tempfile
from typing import List

import mitogen.core

# from mitogen.core import Blob
from mitogen.master import Broker, Router
from mitogen.select import Select

from progfiguration.inventory import Inventory
from progfiguration.inventory.nodes import InventoryNode

# from progfiguration.remoting import rfuncs


def configure_mitogen_logging(core_level: int, io_level: int):
    mitogen.core.LOG.setLevel(core_level)
    # mitogen.core.IOLOG.setLevel(io_level)


def generate_known_hosts(nodes: List[InventoryNode]) -> str:
    lines = [n.known_hosts_entry for n in nodes]
    return "\n".join(lines) + "\n"


def somesh(command: str):
    result = subprocess.run(command, capture_output=True, shell=True)
    return {"stdout": result.stdout, "stderr": result.stderr}


def mitogen_example_remote_function():
    return "I am an example function intended to be run on remote hosts by mitogen"


def mitogen_example():
    hostnames = [
        "jesseta.home.micahrl.com",
        "kenasus.home.micahrl.com",
        "zalas.home.micahrl.com",
    ]
    broker = Broker()
    router = Router(broker)

    try:
        # hostname:context pairs
        contexts = {n: router.ssh(hostname=n, username="root", python_path="python3") for n in hostnames}
        # context_id:hostname pairs
        # Used to get the hostname for a given response
        hostname_by_context_id = {context.context_id: hostname for hostname, context in contexts.items()}

        print("Calling a function that's part of the Python standard library which returns a string")
        calls = [ctx.call_async(socket.gethostname) for ctx in contexts.values()]
        for msg in Select(calls):
            hostname = hostname_by_context_id[msg.src_id]
            result = msg.unpickle()
            for line in result.split("\n"):
                print(f"{hostname}: {line}")
            # This works just fine, returns lines like
            #   jesseta.home.micahrl.com: jesseta

        print("Calling a function that's part of the standard lib, with an argument, that returns an int")
        calls = [ctx.call_async(os.system, "whoami") for ctx in contexts.values()]
        for msg in Select(calls):
            hostname = hostname_by_context_id[msg.src_id]
            result = msg.unpickle()
            print(f"{hostname}: {result}")
            # This works but doesn't show the output
            # The result is just the exist code of the command, '0' on success

        print("Calling a function that's part of the standard lib, with an argument, that returns an object")
        calls = [ctx.call_async(subprocess.run, "whoami") for ctx in contexts.values()]
        for msg in Select(calls):
            hostname = hostname_by_context_id[msg.src_id]
            # This fails on the call to .unpickle() with a message:
            #   mitogen.core.StreamError: cannot unpickle 'commands'/'CompletedProcess'
            # result = msg.unpickle()
            # print(f"{hostname}: {result}")
            # We can see the 'msg' object, which converts to string like
            #   Message(0, 3, 3, 1005, 0, b'\x80\x02ccommands\nCompletedProcess\nq\x00)\x81q\x01}q\x02(X\x04\x00\x00\x00argsq\x03'..113)
            print(f"{hostname}: {msg}")

        # This doesn't work at all, showing log lines including
        #   [2022-10-05 17:34:28,245] [mitogen.importer.[ssh.kenasus.home.micahrl.com]] [DEBUG] progfiguration.remoting is submodule of a locally loaded package
        # and
        #   mitogen.core.CallError: builtins.ModuleNotFoundError: No module named 'progfiguration.remoting'
        # (progfiguration.remoting is the name of this module)
        print("Calling a function defined in this Python module")
        calls = [ctx.call_async(mitogen_example_remote_function) for ctx in contexts.values()]
        for msg in Select(calls):
            hostname = hostname_by_context_id[msg.src_id]
            result = msg.unpickle()
            print(f"{hostname}: {result}")

    finally:
        broker.shutdown()


def command(inventory: Inventory, nodes: List[str], groups: List[str], cmd: str):
    for group in groups:
        nodes += inventory.group_members[group]
    nodes = set(nodes)
    nmods = [inventory.node(n) for n in nodes]
    addrs = [n.node.address for n in nmods]

    # address/fingerprint pairs in a dict
    hosts = {n.node.address: n.node.known_hosts_entry for n in nmods}

    with tempfile.NamedTemporaryFile() as tmpfile:
        tmpfile.write(generate_known_hosts([n.node for n in nmods]).encode())
        tmpfile.seek(0)

        # print("known_hosts")
        # subprocess.run(["cat", tmpfile.name])
        # print("end known_hosts")

        broker = Broker()
        router = Router(broker)

        try:
            # hostname:context pairs
            contexts = {
                n.node.address: router.ssh(
                    hostname=n.node.address,
                    username=n.node.user,
                    ssh_args=["-o", f"UserKnownHostsFile={tmpfile.name}"],
                    python_path="python3",  # TODO: make this generic
                )
                for n in nmods
            }
            # context_id:hostname pairs
            # Used to get the hostname for a given response
            hostname_by_context_id = {context.context_id: hostname for hostname, context in contexts.items()}

            # calls = [ctx.call_async(socket.gethostname) for ctx in contexts.values()]
            # for msg in Select(calls):
            #     hostname = hostname_by_context_id[msg.src_id]
            #     result = msg.unpickle()
            #     for line in result.split("\n"):
            #         print(f"{hostname}: {line}")

            calls = [ctx.call_async(os.system, cmd) for ctx in contexts.values()]
            for msg in Select(calls):
                hostname = hostname_by_context_id[msg.src_id]
                result = msg.unpickle()
                print(f"{hostname}: {result}")

            # calls = [ctx.call_async(subprocess.run, cmd, capture_output=True, shell=True) for ctx in contexts.values()]

        finally:
            broker.shutdown()
