# micahrl.com DNS

I use AWS Route53.

To deploy:

    aws cloudformation deploy \
        --stack-name MicahrlDotCom \
        --capabilities CAPABILITY_NAMED_IAM \
        --template-file ./MicahrlDotCom.cfn.yaml

To update once deployed:

    aws cloudformation update-stack \
        --stack-name MicahrlDotCom \
        --capabilities CAPABILITY_NAMED_IAM \
        --template-body "$(cat ./MicahrlDotCom.cfn.yaml)"
