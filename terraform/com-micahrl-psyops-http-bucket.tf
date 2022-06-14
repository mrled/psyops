# S3 bucket to back psyops.micahrl.com
#
# Create an S3 bucket and a group with permission to write to it,
# as well as intermediate objects required to connect them together.
#
# Create an IAM user, but don't create any security keys.
# We assume that is done in the AWS web console.

locals {
  psyops_http_bucket_domain = "psyops.micahrl.com"
  psyops_http_bucket_name = "com-micahrl-psyops-http-bucket"
  psyops_http_bucket_deployer_policy_name = "com-micahrl-psyops-http-bucket-deployer-policy"
  psyops_http_bucket_deployer_group_name = "com-micahrl-psyops-http-bucket-deployers"
  psyops_http_bucket_deployer_user_name = "com-micahrl-psyops-http-bucket-deployer"
}

resource "aws_s3_bucket" "psyops_http_bucket" {
  bucket = local.psyops_http_bucket_name
}

resource "aws_s3_bucket_acl" "psyops_http_bucket_acl" {
  bucket = aws_s3_bucket.psyops_http_bucket.id
  acl = "public-read"
}

resource "aws_s3_bucket_website_configuration" "psyops_http_bucket_website_configuration" {
  bucket = aws_s3_bucket.psyops_http_bucket.bucket
  index_document {
    suffix = "index.html"
  }
  error_document {
    key = "error.html"
  }

  # routing_rule {
  #   condition {
  #     key_prefix_equals = "docs/"
  #   }
  #   redirect {
  #     replace_key_prefix_with = "documents/"
  #   }
  # }
}

resource "aws_s3_bucket_policy" "psyops_http_bucket_website_site_policy" {
  bucket = aws_s3_bucket.psyops_http_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource = [
          aws_s3_bucket.psyops_http_bucket.arn,
          "${aws_s3_bucket.psyops_http_bucket.arn}/*",
        ]
      },
    ]
  })
}

resource "aws_s3_bucket_cors_configuration" "psyops_http_bucket_cors_config" {
  bucket = aws_s3_bucket.psyops_http_bucket.bucket

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["*"]
    # expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_iam_policy" "psyops_http_bucket_deployer_group_policy" {
  name = local.psyops_http_bucket_deployer_policy_name
  lifecycle {
    create_before_destroy = false
  }
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # {
      #   Effect: "Allow",
      #   Action: "s3:GetObject",
      #   Resource: [
      #     "${aws_s3_bucket.psyops_http_bucket.arn}/*"
      #   ]
      # },
      {
        Effect: "Allow",
        Action: [
            "s3:GetBucketLocation",
            "s3:ListBucket"
        ],
        Resource: "${aws_s3_bucket.psyops_http_bucket.arn}"
      },
      {
        Effect: "Allow",
        Action: [
            "s3:PutObject",
            "s3:DeleteObject",
            "s3:GetObject"
        ],
        Resource: [
            "${aws_s3_bucket.psyops_http_bucket.arn}/*",
            "${aws_s3_bucket.psyops_http_bucket.arn}",
        ]
      }
    ]
  })
}

resource "aws_iam_group" "psyops_http_bucket_deployer_group" {
  name = local.psyops_http_bucket_deployer_group_name
}

resource "aws_iam_group_policy_attachment" "psyops_http_bucket_attachment" {
  group = aws_iam_group.psyops_http_bucket_deployer_group.name
  policy_arn = aws_iam_policy.psyops_http_bucket_deployer_group_policy.arn
}

resource "aws_iam_user" "psyops_http_bucket_deployer_user" {
  name = local.psyops_http_bucket_deployer_user_name
}

resource "aws_iam_group_membership" "psyops_http_bucket_deployer_gmemb" {
  name = "${aws_iam_group.psyops_http_bucket_deployer_group.name}-membership"
  users = ["${aws_iam_user.psyops_http_bucket_deployer_user.name}"]
  group = "${aws_iam_group.psyops_http_bucket_deployer_group.name}"
}

# data "aws_route53_record" "psyops_http_bucket_record" {
#   zone_id = "Z3HVGWA7OSS1TK" # the micahrl.com root zone
#   name = local.psyops_http_bucket_domain
# }

# resource "aws_acm_certificate" "psyops_http_bucket_tls_certificate" {
#   provider = aws.acm_provider
#   domain_name = local.psyops_http_bucket_uri
#   validation_method = "DNS"
#   lifecycle {
#     create_before_destroy = true
#   }
# }

# # Uncomment the validation_record_fqdns line if you do DNS validation instead of Email.
# resource "aws_acm_certificate_validation" "cert_validation" {
#   provider = aws.acm_provider
#   certificate_arn = aws_acm_certificate.ssl_certificate.arn
#   # validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
#   validation_record_fqdns = [aws_route53_record.psyops_http_bucket_record.cert_validation.fqdn]
# }
