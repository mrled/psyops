import logging

import psycopg2


def get_connection(args):
    """
    Returns a new psycopg2 connection using command-line arguments
    for host, port, user, password, and dbname.
    """
    logging.debug("Establishing database connection.")
    return psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.dbname,
    )
