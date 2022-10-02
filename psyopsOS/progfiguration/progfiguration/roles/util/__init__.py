"""Generic utility functions"""


from io import StringIO
from typing import Dict


import yaml


def yaml_dump_str(data, yaml_dump_kwargs: Dict) -> str:
    """Get YAML string from data

    Like yaml.dump() except it doesn't save to a file
    """
    string_stream = StringIO()
    yaml.dump(data, string_stream, **yaml_dump_kwargs)
    yaml_document_string = string_stream.getvalue()
    string_stream.close()
    return yaml_document_string
