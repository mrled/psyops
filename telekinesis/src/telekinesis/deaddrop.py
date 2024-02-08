"""Manage the S3 bucket used for psyopsOS, called deaddrop"""

import hashlib
import os
from pathlib import Path
import pprint

import boto3

from telekinesis import tklogger


def makesession(aws_access_key_id, aws_secret_access_key, aws_region):
    """Return a boto3 session"""
    import boto3

    if aws_access_key_id is None:
        aws_access_key_id = os.environ["AWS_ACCESS_KEY_ID"]
    if aws_secret_access_key is None:
        aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"]
    return boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


class S3PriceWarningError(Exception):
    pass


def s3_list_remote_files(session: boto3.Session, bucket_name: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return a list of all remote files.

    Return a tuple[{filepath: ETag}, {filepath: WebsiteRedirectLocation}].
    The first item in the tuple represents regular files mapped to their MD5 checksum.
    The second item in the tuple represents symlinks mapped to their target.
    """

    s3 = session.client("s3")

    # Get list of all remote files in S3 bucket with their ETags
    # Note that S3 API calls do cost money,
    # but we don't expect it to be very much.
    # Currently, GET requests cost $0.0004 per 1,000 requests.
    s3_price_per_request = 0.0004 / 1000
    # At that price, 1m requests is $0.40.
    too_many_requests = 1_000_000

    files = {}
    redirects = {}

    paginator = s3.get_paginator("list_objects_v2")
    objctr = 0
    api_calls_per_obj = 2  # one to .get() and one to .head_object()
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get("Contents", []):
            objctr += 1
            callctr = objctr * api_calls_per_obj
            filepath = obj["Key"]
            md5sum = obj["ETag"].strip('"')
            head = s3.head_object(Bucket=bucket_name, Key=obj["Key"])
            redirect = head.get("WebsiteRedirectLocation", "")
            if redirect:
                redirects[filepath] = redirect
            else:
                files[filepath] = md5sum
            if callctr > too_many_requests:
                raise S3PriceWarningError(
                    f"Got {objctr} objects using at least {callctr} API calls from S3 so far, this loop just cost you at least ${callctr * s3_price_per_request}."
                )

    return (files, redirects)


def compute_md5(file: Path):
    """Compute the MD5 checksum of a file"""
    hash_md5 = hashlib.md5()
    with file.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def s3_forcepull_directory(session: boto3.Session, bucket_name: str, local_directory: Path):
    """Force-pull a directory from S3, deleting any local files that are not in the bucket

    Use MD5 checksums to determine whether a file has been modified locally and needs to be re-downloaded.
    Note that we assume the ETag is the MD5 checksum, which is only true when not using multi-part upload.
    We don't use it in psyopsOS.
    """
    s3 = session.client("s3")

    # Download files from bucket
    remote_files = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get("Contents", []):
            remote_files.add(obj["Key"])
            local_file_path = local_directory / obj["Key"]

            # Checksum comparison
            should_download = False
            if local_file_path.exists():
                local_checksum = compute_md5(local_file_path)
                remote_checksum = obj["ETag"].strip('"')
                should_download = local_checksum != remote_checksum
            else:
                should_download = True

            # Download file if it doesn't exist or checksum is different
            if should_download:
                print(f"Downloading {obj['Key']}...")
                local_file_path.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(bucket_name, obj["Key"], local_file_path.as_posix())

    # Delete local files not present in bucket
    local_files = set()
    directories = set()
    for local_file_path in local_directory.rglob("*"):
        if local_file_path.is_file():
            relative_path = str(local_file_path.relative_to(local_directory))
            local_files.add(relative_path)

            if relative_path not in remote_files:
                print(f"Deleting local file {relative_path}...")
                local_file_path.unlink()
        elif local_file_path.is_dir():
            directories.add(local_file_path)

    # Delete empty directories
    for directory in sorted(directories, key=lambda x: len(x.parts), reverse=True):
        if not any(directory.iterdir()):
            print(f"Deleting empty directory {directory}...")
            directory.rmdir()


deaddrop_error_html = """
<html>
  <head>
    <title>PSYOPS Error</title>
  </head>
  <body>
    <h1>PSYOPS Error</h1>
    <p>See u on <a href="/">the root page</a>.</p>
  </body>
</html>
"""

deaddrop_index_html = """
<html>
  <head>
    <title>PSYOPS</title>
  </head>
  <body>
    <h1>PSYOPS</h1>
    <p>This site is used for psyopsOS.</p>
    <p>See the <a href="https://me.micahrl.com/projects/psyopsos/">psyopsOS project page</a> for more information, links to code, etc.</p>
  </body>
</html>
"""


def s3_forcepush_directory(session: boto3.Session, bucket_name: str, local_directory: Path):
    """Force-push a directory to S3, deleting any remote files that are not in the local directory"""
    s3 = session.client("s3")

    # Write local error and index pages
    with open(local_directory / "error.html", "w") as f:
        f.write(deaddrop_error_html)
    with open(local_directory / "index.html", "w") as f:
        f.write(deaddrop_index_html)

    # Get list of all remote files in S3 bucket with their ETags
    remote_files, _ = s3_list_remote_files(session, bucket_name)
    remote_files_list = list(remote_files.keys())

    # Upload local files to S3 if they are different or don't exist remotely
    local_files_relpath_list = []
    for local_file_path in list(local_directory.rglob("*")):
        # Ignore directories, as there is no concept of directories in S3
        if not local_file_path.is_file():
            continue

        relative_path = str(local_file_path.relative_to(local_directory))

        local_files_relpath_list.append(relative_path)
        local_checksum = compute_md5(local_file_path)

        exists_remotely = relative_path in remote_files_list
        remote_checksum = remote_files.get(relative_path, "NONE")
        checksum_matches = local_checksum == remote_checksum
        tklogger.debug(
            f"path relative/existsremote: {relative_path}/{exists_remotely}, checksum local/remote/matches: {local_checksum}/{remote_checksum}/{checksum_matches}"
        )

        if exists_remotely and checksum_matches:
            print(f"Skipping {relative_path} because it is already up to date.")
        else:
            print(f"Uploading {relative_path}...")
            extra_args = {}

            # If you don't do this, browsing to these files will download them without displaying them.
            # We mostly just care about this for the index/error html files.
            if local_file_path.as_posix().endswith(".html"):
                extra_args["ContentType"] = "text/html"

            s3.upload_file(
                Filename=local_file_path.as_posix(), Bucket=bucket_name, Key=relative_path, ExtraArgs=extra_args
            )

    # Determine which remote files are not present locally
    files_to_delete = [f for f in remote_files_list if f not in local_files_relpath_list]

    # Delete files from S3 bucket not present in local directory
    for file_key in files_to_delete:
        print(f"Deleting remote file {file_key}...")
        s3.delete_object(Bucket=bucket_name, Key=file_key)
