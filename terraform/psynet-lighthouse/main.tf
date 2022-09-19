# Provisioning lighthouses for the psyopsOS Nebula overlay network

variable "digital_ocean_token" {
  description = "A private access token for your DO account."
  sensitive = true
}

variable "digital_ocean_ssh_key_name" {
  description = "The name in DO of an SSH public key that is already added to your account."
  default = "conspirator@PSYOPS"
}

terraform {
  required_providers {
    digitalocean = {
      source = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {
  token = var.digital_ocean_token
}

data "digitalocean_ssh_key" "terraform" {
  name = var.digital_ocean_ssh_key_name
}

resource "digitalocean_droplet" "lighthouse1_droplet" {
  image = "debian-11-x64"
  name = "psynet-lighthouse1"
  region = "nyc1"
  size = "s-1vcpu-512mb-10gb"

  ssh_keys = [
    data.digitalocean_ssh_key.terraform.id
  ]
}

resource "digitalocean_droplet" "lighthouse2_droplet" {
  image = "debian-11-x64"
  name = "psynet-lighthouse2"
  region = "sfo3"
  size = "s-1vcpu-512mb-10gb"

  ssh_keys = [
    data.digitalocean_ssh_key.terraform.id
  ]
}

output "lighthouse1_ip_address" {
  value = "${digitalocean_droplet.lighthouse1_droplet.ipv4_address}"
}

output "lighthouse2_ip_address" {
  value = "${digitalocean_droplet.lighthouse2_droplet.ipv4_address}"
}
