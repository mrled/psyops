# third-jersey-deployments - A shared deployment resource

This is shared infrastructure for my deployments.

It is designed for providing specific objects to use when deploying.
For instance, SSH key fingerprints can be uploaded to this bucket by an instance when it gets created,
so that we can SSH to the instance without having to TOFU.

To deploy:

    aws cloudformation deploy \
        --stack-name ThirdJersey \
        --template-file ./third-jersey-deployments.cfn.yaml

To update once deployed:

    aws cloudformation update-stack \
        --stack-name ThirdJersey \
        --template-body "$(cat ./third-jersey-deployments.cfn.yaml)"
