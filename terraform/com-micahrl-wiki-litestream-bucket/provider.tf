
provider "aws" {
  # I think I don't have to set these explicitly, but doing it to remind myself
  shared_credentials_files = ["~/.aws/credentials"]
  shared_config_files = ["~/.aws/config"]
}