# Litestream backup bucket for wiki.micahrl.com
#
# Create an S3 bucket and a group with permission to write to it,
# as well as intermediate objects required to connect them together.
#
# Create an IAM user, but don't create any security keys.
# We assume that is done in the AWS web console.

provider "aws" {
  # I think I don't have to set these explicitly, but doing it to remind myself
  shared_credentials_files = ["~/.aws/credentials"]
  shared_config_files = ["~/.aws/config"]
}

locals {
  bucket_name = "com-micahrl-wiki-litestream-bucket"
  backup_writer_policy_name = "com-micahrl-wiki-litestream-bucket-backup-writer-policy"
  backup_writer_group_name = "com-micahrl-wiki-litestream-bucket-backup-writers"
  backup_writer_user_name = "com-micahrl-wiki-litestream-bucket-backup-writer"
}

resource "aws_s3_bucket" "bucket" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_acl" "acl" {
  bucket = aws_s3_bucket.bucket.id
  acl = "private"
}

# Minimum policy taken from <https://tip.litestream.io/guides/s3/>
resource "aws_iam_policy" "policy" {
  name = local.backup_writer_policy_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect: "Allow",
        Action: [
            "s3:GetBucketLocation",
            "s3:ListBucket"
        ],
        Resource: "${aws_s3_bucket.bucket.arn}"
      },
      {
        Effect: "Allow",
        Action: [
            "s3:PutObject",
            "s3:DeleteObject",
            "s3:GetObject"
        ],
        Resource: [
            "${aws_s3_bucket.bucket.arn}/*",
            "${aws_s3_bucket.bucket.arn}",
        ]
      }
    ]
  })
}

resource "aws_iam_group" "group" {
  name = local.backup_writer_group_name
}

resource "aws_iam_group_policy_attachment" "attachment" {
  group = aws_iam_group.group.name
  policy_arn = aws_iam_policy.policy.arn
}

resource "aws_iam_user" "user" {
  name = local.backup_writer_user_name
}

resource "aws_iam_group_membership" "gmemb" {
  name = "${aws_iam_group.group.name}-membership"
  users = ["${aws_iam_user.user.name}"]
  group = "${aws_iam_group.group.name}"
}
