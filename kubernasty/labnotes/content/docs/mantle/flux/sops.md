---
title: Encryption with SOPS
weight: 10
---

Before setting up [Flux]({{< ref "flux-gitops" >}}),
we need to configure SOPS locally.

* Create an `age` key for Kubernasty's `sops` encryption.
  ```sh
  age-keygen -o flux.agekey
  ```
* Do NOT commit the Age private key to your Git repo
  (though you might want to save it to your password manager).
* Create a SOPS config file under {{< repolink "kubernasty/.sops.yaml" >}},
  replacing PUBKEY with the public key from Age in the previous step:
  ```yaml
  creation_rules:
    - path_regex: .*.yaml
      encrypted_regex: ^(data|stringData)$
      age: PUBKEY
  ```
  With that file in place,
  sops will find it when you're trying to encrypt any item from a pwd of `kubernasty/`
  or any of its subdirectories.
* Encrypt files with `sops -e ...`,
  and decrypt them with `sops -d ...`
  (see below).
* **Make sure to only commit encrypted secrets to Git**.
  You may want to set up a git hook that enforces this.

Examples working with SOPS:

```sh
# Create a secrets file... this is just an example.
# Remember that it must be created in the same namespace as the service that will use it.
cat > Secret.yaml <<EOF
---
kind: Secret
apiVersion: v1
type: Opaque
metadata:
  name: example-credential-name
  namespace: asdfwhatever
stringData:
  secretName: s3cr3tV@lue
EOF

# Use sops to encrypt it
# We save it to the right location for the psyops container, adjust to your own needs if not using psyops.
sops --encrypt Secret.yaml > Secret.encrypted.yaml
# Then you can delete the tmp secret file
rm Secret.yaml

# You could instead encrypt or decrypt a file in-place
sops --encrypt --in-place Secret.yaml

# Use sops to decrypt the encrypted file for viewing.
sops --decrypt Secret.encrypted.yaml

# Use sops to decrypt the file to apply with kubectl
sops --decrypt Secret.encrypted.yaml |
  kubectl apply -f -
```

