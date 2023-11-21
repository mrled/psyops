"""Manage the S3 bucket used for psyopsOS, called deaddrop"""

import hashlib
import os
from pathlib import Path

import boto3


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


def list_files(session: boto3.Session, bucket: str):
    s3 = session.client("s3")
    response = s3.list_objects_v2(Bucket=bucket)
    if "Contents" in response:
        for item in response["Contents"]:
            print(item["Key"])
    else:
        print("Bucket is empty or does not exist.")


def s3_upload_directory(directory, bucketname):
    """Upload a directory to S3 using AWS creds from ~/.aws

    TODO: keep track of all uploaded files, then at the end list all files in the bucket and delete any we didn't upload
    """
    import boto3

    s3client = boto3.client("s3")
    for root, _, files in os.walk(directory):
        for filename in files:
            local_filepath = os.path.join(root, filename)
            relative_filepath = os.path.relpath(local_filepath, directory)
            print(f"Uploading {local_filepath}...")
            extra_args = {}
            # If you don't do this, browsing to these files will download them without displaying them.
            # We mostly just care about this for the index/error html files.
            if filename.endswith(".html"):
                extra_args["ContentType"] = "text/html"
            s3client.upload_file(local_filepath, bucketname, relative_filepath, ExtraArgs=extra_args)


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
    remote_files = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get("Contents", []):
            remote_files[obj["Key"]] = obj["ETag"].strip('"')

    # Upload local files to S3 if they are different or don't exist remotely
    for local_file_path in local_directory.rglob("*"):
        if local_file_path.is_file():
            relative_path = str(local_file_path.relative_to(local_directory))
            local_checksum = compute_md5(local_file_path)

            if relative_path not in remote_files or local_checksum != remote_files[relative_path]:
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
    local_files = {path.as_posix() for path in local_directory.rglob("*") if path.is_file()}
    files_to_delete = remote_files - local_files

    # Delete files from S3 bucket not present in local directory
    for file_key in files_to_delete:
        print(f"Deleting remote file {file_key}...")
        s3.delete_object(Bucket=bucket_name, Key=file_key)
