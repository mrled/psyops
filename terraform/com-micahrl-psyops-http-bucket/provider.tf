
provider "aws" {
  # I think I don't have to set these explicitly, but doing it to remind myself
  shared_credentials_files = ["~/.aws/credentials"]
  shared_config_files = ["~/.aws/config"]
}

# Certificates used with CloudFront must be in us-east-1
# wtf lol
# <https://aws.amazon.com/premiumsupport/knowledge-center/migrate-ssl-cert-us-east/>
# <https://github.com/jareware/howto/blob/master/Using%20AWS%20ACM%20certificates%20with%20Terraform.md>
provider "aws" {
  alias = "acm_provider"
  shared_credentials_files = ["~/.aws/credentials"]
  shared_config_files = ["~/.aws/config"]
  region = "us-east-1"
}
