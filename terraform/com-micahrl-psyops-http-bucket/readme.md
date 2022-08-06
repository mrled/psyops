# psyops http bucket terraform

## Initial deployment

### terraform can't give full plan

When deploying from scratch, terraform cannot give you a full plan.

```
│ Error: Invalid for_each argument
│
│   on com-micahrl-psyops-http-bucket.tf line 136, in resource "aws_route53_record" "psyops_http_bucket_record":
│  136:   for_each = {
│  137:     for dvo in aws_acm_certificate.cert.domain_validation_options : dvo.domain_name => {
│  138:       name   = dvo.resource_record_name
│  139:       record = dvo.resource_record_value
│  140:       type   = dvo.resource_record_type
│  141:     }
│  142:   }
│     ├────────────────
│     │ aws_acm_certificate.cert.domain_validation_options is a set of object, known only after apply
│
│ The "for_each" map includes keys derived from resource attributes that cannot be determined until apply, and so Terraform cannot determine the full set of keys that will identify the instances
│ of this resource.
│
│ When working with unknown values in for_each, it's better to define the map keys statically in your configuration and place apply-time results only in the map values.
│
│ Alternatively, you could use the -target planning option to first apply only the resources that the for_each value depends on, and then apply a second time to fully converge.
```

Use `-target` as it suggests.

```
terraform plan -target aws_acm_certificate.cert
```

### CNAME created separately

I manage this zone in CloudFormation, so I set the CNAME there.
You have to run `terraforom apply -target` as above to deploy the bucket and its configuration,
then set the CNAME in the CFN template and apply it,
then import the CNAME with
`terraform import 'aws_route53_record.psyops_http_bucket_record["com-micahrl-psyops-http-bucket.s3.amazonaws.com"]'  Z3HVGWA7OSS1TK_psyops.micahrl.com_CNAME`,
then come back here and run `terraform apply`

UPDATE: I think this is unnecessary?

### Set the CNAME in the CloudFormation template

This terraform creates the CloudFront distribution, which has a URL like `asdfqwezxcv.cloudfront.net`.
Make `psyops.micahrl.com` a CNAME to that domain.

## Links

- <https://medium.com/runatlantis/hosting-our-static-site-over-ssl-with-s3-acm-cloudfront-and-terraform-513b799aec0f>
