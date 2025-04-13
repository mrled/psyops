import datetime


def firwmare_update_timestamp(dt: datetime.datetime) -> str:
    """Get a timestamp in our standard format for the last updated time."""
    return dt.strftime("%Y%m%d-%H%M%S")
