# cli.py
import sys
import pdb
import logging
import traceback
import argparse

from knpl_macrofactor.processing import check_file_processed, mark_file_processed
from knpl_macrofactor.dataimport import import_xlsx
import os


def idb_excepthook(exc_type, exc_value, tb):
    """
    Post-mortem interactive debugger if an unhandled exception occurs
    and we're in a TTY.
    """
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        # If we're in an interactive shell already or no TTY, just do normal traceback
        sys.__excepthook__(exc_type, exc_value, tb)
    else:
        traceback.print_exception(exc_type, exc_value, tb)
        print()
        pdb.pm()


def main():
    parser = argparse.ArgumentParser(
        description="CLI for Macrofactor data pipeline operations."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging."
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Drop into interactive debugger on uncaught exception.",
    )

    # Common database arguments
    parser.add_argument("--host", help="Database host")
    parser.add_argument("--port", help="Database port")
    parser.add_argument("--user", help="Database user")
    parser.add_argument("--password", help="Database password")
    parser.add_argument("--dbname", help="Database name")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check-processed
    p_check = subparsers.add_parser(
        "check-processed", help="Check if a file has already been processed."
    )
    p_check.add_argument(
        "--file-key", required=True, help="Key/name of the file to check."
    )

    # Subcommand: mark-processed
    p_mark = subparsers.add_parser(
        "mark-processed", help="Mark a file as processed in the DB."
    )
    p_mark.add_argument(
        "--file-key", required=True, help="Key/name of the file to mark."
    )

    # Subcommand: import-xlsx
    p_import = subparsers.add_parser(
        "import-xlsx", help="Import the macrofactor.xlsx data."
    )
    p_import.add_argument(
        "--xlsx-file", required=True, help="Path to the macrofactor Excel file."
    )

    args = parser.parse_args()

    if not args.host:
        args.host = os.getenv("PGHOST", "localhost")
    if not args.port:
        args.port = os.getenv("PGPORT", "5432")
    if not args.user:
        args.user = os.getenv("PGUSER", "postgres")
    if not args.password:
        args.password = os.getenv("PGPASSWORD", "postgres")
    if not args.dbname:
        args.dbname = os.getenv("PGDATABASE", "postgres")

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.debug:
        sys.excepthook = idb_excepthook

    if args.command == "check-processed":
        try:
            processed = check_file_processed(args)
            print(str(processed))
        except Exception as e:
            logging.exception("An error occurred.")
            print(f"error: {e}")
            sys.exit(1)

    elif args.command == "mark-processed":
        mark_file_processed(args)
        print("ok")

    elif args.command == "import-xlsx":
        import_xlsx(args)
        print("ok")
