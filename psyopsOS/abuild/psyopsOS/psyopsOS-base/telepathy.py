#!/usr/bin/env python3

"""Telepathy: An extensible remote viewing system for psyopsOS

Goals:

* A single script that can be included in the psyopsOS-base package
* Extensible by adding plugin scripts to /etc/psyopsOS/telepathy.d
* Non-sensitive information available without authentication only (for now?)

Plugins:

* A single Python script in /etc/psyopsOS/telepathy.d
* Must have a `handler()` function, which may optionally accept arguments
"""

import argparse
import importlib.util
import logging
import os
import pdb
import sys
import traceback
import typing
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def idb_excepthook(type, value, tb):
    """Call an interactive debugger in post-mortem mode

    If you do "sys.excepthook = idb_excepthook", then an interactive debugger
    will be spawned at an unhandled exception
    """
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        traceback.print_exception(type, value, tb)
        print
        pdb.pm()


def broken_pipe_handler(
    func: Callable[[typing.List[str]], int], *arguments: typing.List[str]
) -> int:
    """Handler for broken pipes

    Wrap the main() function in this to properly handle broken pipes
    without a giant nastsy backtrace.
    The EPIPE signal is sent if you run e.g. `script.py | head`.
    Wrapping the main function with this one exits cleanly if that happens.

    See <https://docs.python.org/3/library/signal.html#note-on-sigpipe>
    """
    try:
        returncode = func(*arguments)
        sys.stdout.flush()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        # Convention is 128 + whatever the return code would otherwise be
        returncode = 128 + 1
    return returncode


def start_server(bind_host: str, bind_port: int):
    """Start the HTTP server"""
    server_address = (bind_host, bind_port)
    httpd = HTTPServer(server_address, None)
    httpd.serve_forever()


class TelepathyRequestHandler(BaseHTTPRequestHandler):
    """Handle Telepathy HTTP requests"""

    plugins = {}

    def do_GET(self):
        """Handle GET requests"""

        parsed_url = urlparse(self.path)
        path = parsed_url.path
        splitpath = path.strip("/").split("/")
        params = parse_qs(parsed_url.query)

        builtin_routes = {
            "/": self.handle_root_index,
            "/hostname": self.handle_hostname,
        }

        if path in builtin_routes:
            builtin_routes[self.path](**params)
            return
        elif splitpath[0] == "plugins":
            if len(splitpath) == 1:
                return self.handle_success(200, ", ".join(self.plugins.keys()))
            if len(splitpath) > 2:
                return self.handle_error(400, "Invalid plugin path")
            plugin_name = splitpath[1]
            if plugin_name not in self.plugins:
                return self.handle_error(404, "Plugin not found")
            if "handler" not in dir(self.plugins[plugin_name]):
                return self.handle_error(
                    500, "Plugin exists but has no handler function"
                )
            return self.handle_success(200, self.plugins[plugin_name].handler(**params))

        return self.handle_error(404, "Not found")

    def handle_error(self, code: int, message: str):
        """Handle errors"""
        logger.error(f"Error handling request for path {self.path}: {code} {message}")
        message += "\n"
        self.send_error(code, message)

    def handle_success(self, code: int, result: str):
        """Handle success"""
        logger.info(
            f"Handling request for path {self.path} with code {code} and result: {result}"
        )
        self.send_response(code)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        result += "\n"
        self.wfile.write(result.encode())

    def handle_root_index(self):
        """Handle the root index page"""
        self.handle_success(200, "Welcome to Telepathy")

    def handle_hostname(self):
        """Return the hostname

        Useful for nonstandard IP addresses, especially floating addresses like for haproxy or kube-vip
        """
        self.handle_success(200, os.uname().nodename)


def load_plugins(plugins_directory: str) -> typing.Dict[str, typing.Any]:
    """Load plugins from a directory

    Load them once at startup time
    """
    plugins = {}
    if os.path.exists(plugins_directory):
        for plugin in os.listdir(plugins_directory):
            if not plugin.endswith(".py"):
                continue
            plugin_name = plugin[:-3]
            plugin_path = os.path.join(plugins_directory, plugin)
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            plugins[plugin_name] = module
    logger.info(f"Loaded plugins from {plugins_directory}: {', '.join(plugins.keys())}")
    return plugins


def server(host: str, port: int, plugins: typing.Dict[str, typing.Any]):
    """Start the HTTP server"""

    # This is somewhat unusual, but because of the way BaseHTTPRequestHandler works,
    # we have to replace the .plugins _class variable_
    TelepathyRequestHandler.plugins = plugins

    server_address = (host, port)
    httpd = HTTPServer(server_address, TelepathyRequestHandler)

    logger.info(f"Starting server on {host}:{port}")
    httpd.serve_forever()


def parseargs(arguments: typing.List[str]):
    """Parse program arguments"""
    parser = argparse.ArgumentParser(description="Python command line script template")
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Launch a debugger on unhandled exception",
    )
    parser.add_argument(
        "--plugins-directory",
        default="/etc/psyopsOS/telemetry.d",
        help="Location of plugins directory",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument(
        "--port",
        default=7453,
        type=int,
        help="Bind port; default is SIKE on a telephone keypad",
    )
    parsed = parser.parse_args(arguments)
    return parsed


def main(*arguments):
    """Main program"""
    parsed = parseargs(arguments[1:])
    if parsed.debug:
        sys.excepthook = idb_excepthook
    plugins = load_plugins(parsed.plugins_directory)
    server(parsed.host, parsed.port, plugins)


if __name__ == "__main__":
    exitcode = broken_pipe_handler(main, *sys.argv)
    sys.exit(exitcode)
