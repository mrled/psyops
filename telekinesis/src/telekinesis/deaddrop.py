"""Manage the S3 bucket used for psyopsOS, called deaddrop"""

import hashlib
import os
from pathlib import Path
from typing import Union

import boto3

from telekinesis import tklogger


def makesession(aws_access_key_id, aws_secret_access_key, aws_region):
    """Return a boto3 session"""
    if aws_access_key_id is None:
        aws_access_key_id = os.environ["AWS_ACCESS_KEY_ID"]
    if aws_secret_access_key is None:
        aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"]
    session = boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    tklogger.debug(f"Created boto3 session")
    return session


class S3PriceWarningError(Exception):
    pass


def s3_list_remote_files(
    session: boto3.Session,
    bucket_name: str,
    too_many_requests=1_000_000,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return a list of all remote files.

    Return a tuple[{filepath: MD5}, {filepath: WebsiteRedirectLocation}].
    The first item in the tuple represents regular files mapped to their MD5 checksum.
    The second item in the tuple represents symlinks mapped to their target.

    We assume the md5 checksums are stored in the metadata of the S3 objects.
    We do NOT use the ETag, which is not the MD5 checksum of the file contents
    for files uploaded as multipart uploads.
    Large files like our OS tarballs are uploaded as multipart uploads automatically by boto3.

    Arguments:
    - session: boto3 session
    - bucket_name: name of the S3 bucket
    - too_many_requests: maximum number of requests before raising a S3PriceWarningError
        At the time of this writing, 1m requests is $0.40.
    """

    s3 = session.client("s3")

    files = {}
    redirects = {}

    paginator = s3.get_paginator("list_objects_v2")
    objctr = 0
    api_calls_per_obj = 2  # one to .get() and one to .head_object()
    tklogger.debug(f"Listing objects in S3 bucket {bucket_name}...")
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get("Contents", []):
            objctr += 1
            callctr = objctr * api_calls_per_obj
            filepath = obj["Key"]
            head = s3.head_object(Bucket=bucket_name, Key=obj["Key"])
            redirect = head.get("WebsiteRedirectLocation", "")
            md5sum = head["Metadata"].get("md5", "")
            if redirect:
                redirects[filepath] = redirect
            else:
                files[filepath] = md5sum
            if callctr > too_many_requests:
                raise S3PriceWarningError(
                    f"We made (at least) {too_many_requests} requests, but haven't enumerated all the files. Raise the too_many_requests linmit if you're sure you want to do this."
                )
    tklogger.debug(f"Found {len(files)} files and {len(redirects)} redirects in S3 bucket {bucket_name}.")

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
    """
    s3 = session.client("s3")

    remote_files, remote_symlinks = s3_list_remote_files(session, bucket_name)

    # Download files from bucket
    for filepath, remote_checksum in remote_files.items():
        local_file_path = local_directory / filepath

        # Checksum comparison
        should_download = True
        if local_file_path.exists():
            local_checksum = compute_md5(local_file_path)
            should_download = local_checksum != remote_checksum

        # Download file if it doesn't exist or checksum is different
        if should_download:
            tklogger.debug(f"Downloading {filepath}...")
            local_file_path.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket_name, filepath, local_file_path.as_posix())

    # Set local symlinks to match remote redirects
    for s3link, s3target in remote_symlinks.items():
        if s3target.startswith("http"):
            tklogger.warning(
                f"Skipping symlink {s3link} -> {s3target} because it is a full URL and not a relative path."
            )
            continue
        local_link = local_directory / s3link
        local_link.parent.mkdir(parents=True, exist_ok=True)
        local_target_abs = local_directory / s3target.lstrip("/")
        local_target = os.path.relpath(local_target_abs.as_posix(), local_link.parent.as_posix())
        if local_link.exists() and local_link.is_symlink() and local_link.resolve() == local_target_abs:
            tklogger.debug(
                f"Skipping symlink {local_link.as_posix()} -> {local_target} because it is already up to date."
            )
        else:
            if local_link.exists():
                local_link.unlink()
            tklogger.debug(f"Creating local symlink {local_link.as_posix()} -> {local_target}")
            os.symlink(local_target, local_link.as_posix())

    # Delete local files not present in bucket
    local_files = set()
    directories = set()
    for local_file_path in local_directory.rglob("*"):
        if local_file_path.is_file():
            relative_path = str(local_file_path.relative_to(local_directory))
            local_files.add(relative_path)
            exists_remotely = relative_path in remote_files.keys() or relative_path in remote_symlinks.keys()
            if not exists_remotely:
                tklogger.debug(f"Deleting local file {relative_path}...")
                local_file_path.unlink()
        elif local_file_path.is_dir():
            directories.add(local_file_path)

    # Delete empty directories
    for directory in sorted(directories, key=lambda x: len(x.parts), reverse=True):
        if not any(directory.iterdir()):
            tklogger.debug(f"Deleting empty directory {directory}...")
            directory.rmdir()


def s3_forcepush_directory(session: boto3.Session, bucket_name: str, local_directory: Path):
    """Force-push a directory to S3, deleting any remote files that are not in the local directory.

    Calculate a local MD5 checksum and add it as metadata to the S3 object.
    We don't use ETag for this because it is not the MD5 checksum of the file contents for files uploaded as multipart uploads.
    """
    s3 = session.client("s3")

    # Get list of all remote files in S3 bucket with their checksums
    remote_files, remote_symlinks = s3_list_remote_files(session, bucket_name)

    # Keep track of local files
    # This includes all files, including symlinks to files,
    # but not directories or symlinks to directories.
    # The loop below also ignores macOS garbage .DS_Store and ._* files
    local_files_relpath_list = []

    # Upload local files to S3 if they are different or don't exist remotely
    for local_file_path in list(local_directory.rglob("*")):
        # Ignore goddamn fucking macOS gunk files
        if local_file_path.name == ".DS_Store":
            continue
        if local_file_path.name.startswith("._"):
            continue

        # Ignore directories, as there is no concept of directories in S3.
        # Note that is_file() returns False for symlinks which point to directories, which is good too.
        if not local_file_path.is_file():
            continue

        relative_path = str(local_file_path.relative_to(local_directory))
        local_files_relpath_list.append(relative_path)

        # Handle symlinks
        if local_file_path.is_symlink():
            target = local_file_path.resolve()
            try:
                reltarget = str(target.relative_to(local_directory))
                # S3 Object Redirects must be absolute paths from bucket root with a leading slash (or a full URL).
                abstarget = f"/{reltarget}"
            except ValueError:
                tklogger.warning(
                    f"Skipping symlink {relative_path} -> {target} because it points outside of the local directory."
                )
                continue
            if relative_path in remote_symlinks and remote_symlinks[relative_path] == abstarget:
                tklogger.debug(f"Skipping symlink {relative_path} -> {abstarget} because it is already up to date.")
            else:
                tklogger.debug(f"Creating S3 Object Redirect for {relative_path} -> {abstarget}")
                s3.put_object(Bucket=bucket_name, Key=relative_path, WebsiteRedirectLocation=abstarget)

        # Handle regular files
        else:
            local_checksum = compute_md5(local_file_path)

            exists_remotely = relative_path in remote_files.keys()
            remote_checksum = remote_files.get(relative_path, "NONE")
            checksum_matches = local_checksum == remote_checksum
            tklogger.debug(
                f"path relative/existsremote: {relative_path}/{exists_remotely}, checksum local/remote/matches: {local_checksum}/{remote_checksum}/{checksum_matches}"
            )

            if exists_remotely and checksum_matches:
                tklogger.debug(f"Skipping {relative_path} because it is already up to date.")
            else:
                tklogger.debug(f"Uploading {relative_path}...")
                extra_args: dict[str, Union[str, dict[str, str]]] = {}

                extra_args["Metadata"] = {"md5": local_checksum}

                # If you don't do this, browsing to these files will download them without displaying them.
                # We mostly just care about this for the index/error html files.
                if local_file_path.as_posix().endswith(".html"):
                    extra_args["ContentType"] = "text/html"

                # Note that upload_file enables multipart uploads for large files by default
                s3.upload_file(
                    Filename=local_file_path.as_posix(), Bucket=bucket_name, Key=relative_path, ExtraArgs=extra_args
                )

    # Delete files from S3 bucket not present in local directory
    files_to_delete = [f for f in remote_files.keys() if f not in local_files_relpath_list]
    for file_key in files_to_delete:
        tklogger.debug(f"Deleting remote file {file_key}...")
        s3.delete_object(Bucket=bucket_name, Key=file_key)

    # Delete redirecting objects from S3 bucket not present as symlinks in local directory
    links_to_delete = [f for f in remote_symlinks.keys() if f not in local_files_relpath_list]
    for link_key in links_to_delete:
        tklogger.debug(f"Deleting remote symlink {link_key}...")
        s3.delete_object(Bucket=bucket_name, Key=link_key)


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


def s3_forcepush_deaddrop(session: boto3.Session, bucket_name: str, local_directory: Path):
    """Force-push the local directory to the deaddrop S3 bucket

    Wrapper function for s3_forcepush_directory that also writes the error and index pages.
    """

    # Write local error and index pages
    with open(local_directory / "error.html", "w") as f:
        f.write(deaddrop_error_html)
    with open(local_directory / "index.html", "w") as f:
        f.write(deaddrop_index_html)

    # Upload
    s3_forcepush_directory(session, bucket_name, local_directory)
