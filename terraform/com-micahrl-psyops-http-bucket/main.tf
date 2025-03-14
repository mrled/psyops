# S3 bucket to back psyops.micahrl.com
#
# Create an S3 bucket and a group with permission to write to it,
# as well as intermediate objects required to connect them together.
#
# Create an IAM user, but don't create any security keys.
# We assume that is done in the AWS web console.
#
# The record for psyops_http_bucket_domain is created separately in a CloudFormation template

locals {
  psyops_http_bucket_domain = "psyops.micahrl.com"
  psyops_http_bucket_name = "com-micahrl-psyops-http-bucket"
  psyops_http_bucket_deployer_policy_name = "com-micahrl-psyops-http-bucket-deployer-policy"
  psyops_http_bucket_deployer_group_name = "com-micahrl-psyops-http-bucket-deployers"
  psyops_http_bucket_deployer_user_name = "com-micahrl-psyops-http-bucket-deployer"
  origin_zone_id = "Z3HVGWA7OSS1TK" # the micahrl.com root zone
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

# This is the record for the certificate validation, NOT the record for psyops_http_bucket_domain
# The record for psyops_http_bucket_domain is defined in a MicahrlDotCom.cfn.yml
# alongside other records in the micahrl.com zone.
resource "aws_route53_record" "psyops_http_bucket_record" {
  for_each = {
    for dvo in aws_acm_certificate.cert.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }
  # allow_overwrite = true
  name = each.value.name
  records = [each.value.record]
  ttl = 300
  type = each.value.type
  zone_id = local.origin_zone_id
}

resource "aws_acm_certificate" "cert" {
  provider = aws.acm_provider
  domain_name = local.psyops_http_bucket_domain
  validation_method = "DNS"
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "cert_validation" {
  provider = aws.acm_provider
  certificate_arn = aws_acm_certificate.cert.arn
  validation_record_fqdns = [for record in aws_route53_record.psyops_http_bucket_record : record.fqdn]
}

resource "aws_cloudfront_distribution" "www_distribution" {
  origin {
    custom_origin_config {
      http_port              = "80"
      https_port             = "443"
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1", "TLSv1.1", "TLSv1.2"]
    }

    domain_name = "${aws_s3_bucket.psyops_http_bucket.website_endpoint}"
    origin_id   = "${local.psyops_http_bucket_domain}"
  }

  enabled             = true
  default_root_object = "index.html"

  default_cache_behavior {
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "${local.psyops_http_bucket_domain}"
    min_ttl                = 0
    default_ttl            = 60
    max_ttl                = 60

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  aliases = ["${local.psyops_http_bucket_domain}"]

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn = "${aws_acm_certificate.cert.arn}"
    ssl_support_method  = "sni-only"
  }
}