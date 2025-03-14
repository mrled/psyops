# psyopsOS datadump

* S3 bucket
* A shared user with read-only access that all nodes can use
* An administrative user that has read-write access to upload new files
* A shared encryption password that s3cmd uses to keep data secret from Amazon

This might contain large binaries like programs or data that are not public,
but that I don't need to keep fully secret.
For instance: Synergy binaries, large language models, etc.

## Initial configuration

* Create an S3 bucket
* Create an IAM key with read-only access, shared to all nodes
* Create an IAM key with read/write access for the controller
* `s3cmd --configure`
    * Use the shared credentials
    * Enter a random value for the encryption password --
      this keeps the data encrypted from Amazon too
* Save the the configuration file to gopass with `gopass insert psyopsos/datadump/s3cfg-shared < ~/.s3cfg`
* Edit the configuration file to use the controller IAM credentials
* Save the config with new credentials to gopass with `gopass insert psyopsos/datadump/s3cfg-controller < ~/.s3cfg`

## Uploading from the controller

Make sure you've got the config file:
`gopass cat psyopsos/datadump/s3cfg-controller > ~/.s3cfg`.

Use normal s3cmd invocations to list files, upload, delete, etc.
E.g. here is uploading a directory called `synergy` recursively to the datadump bucket:

```sh
s3cmd put synergy s3://psyopsos-datadump/synergy
```
