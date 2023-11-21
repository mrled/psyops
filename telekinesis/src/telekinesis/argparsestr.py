"""Retrieve the help string for an argparse parser, recursively.

From <https://me.micahrl.com/blog/pdoc-argparse/>
"""

import argparse


def get_argparse_help_string(name: str, parser: argparse.ArgumentParser, wrap: int = 80) -> str:
    """Generate a docstring for an argparse parser that shows the help for the parser and all subparsers, recursively.

    Based on an idea from <https://github.com/pdoc3/pdoc/issues/89>

    Arguments:
    * `name`: The name of the program
    * `parser`: The parser
    * `wrap`: The number of characters to wrap the help text to (0 to disable)
    """

    def help_formatter(prog):
        return argparse.HelpFormatter(prog, width=wrap)

    def get_parser_help_recursive(parser: argparse.ArgumentParser, cmd: str = "", root: bool = True):
        docstring = ""
        if not root:
            docstring += "\n" + "_" * 72 + "\n\n"
        docstring += f"> {cmd} --help\n"
        parser.formatter_class = help_formatter
        docstring += parser.format_help()

        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for subcmd, subparser in action.choices.items():
                    docstring += get_parser_help_recursive(subparser, f"{cmd} {subcmd}", root=False)
        return docstring

    docstring = get_parser_help_recursive(parser, name)
    return docstring
