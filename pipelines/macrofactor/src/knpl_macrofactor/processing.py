import logging

from knpl_macrofactor.db import get_connection


def check_file_processed(args):
    """
    Checks if file_key is already in macrofactor_files. Returns True or False.
    """
    logging.debug("Checking if file '%s' has been processed.", args.file_key)
    with get_connection(args) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS macrofactor_files (
                    file_key TEXT PRIMARY KEY,
                    imported_at TIMESTAMP DEFAULT NOW()
                );
            """
            )
            cur.execute(
                "SELECT 1 FROM macrofactor_files WHERE file_key = %s", (args.file_key,)
            )
            row = cur.fetchone()
            return bool(row)


def mark_file_processed(args):
    """
    Marks file_key as processed in macrofactor_files.
    """
    logging.debug("Marking file '%s' as processed.", args.file_key)
    with get_connection(args) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS macrofactor_files (
                    file_key TEXT PRIMARY KEY,
                    imported_at TIMESTAMP DEFAULT NOW()
                );
            """
            )
            cur.execute(
                """
                INSERT INTO macrofactor_files (file_key, imported_at)
                VALUES (%s, NOW())
                ON CONFLICT (file_key)
                DO NOTHING;
            """,
                (args.file_key,),
            )
        conn.commit()
    logging.debug("Successfully marked file '%s' as processed.", args.file_key)
