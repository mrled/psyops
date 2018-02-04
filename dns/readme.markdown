# micahrl.com DNS

I use AWS Route53.

To deploy:

    aws cloudformation deploy \
        --stack-name MicahrlDotCom \
        --template-file ./MicahrlDotCom.cfn.yaml \
        --capabilities CAPABILITY_NAMED_IAM

To update once deployed:

    aws cloudformation update-stack \
        --stack-name MicahrlDotCom \
        --template-body "$(cat ./MicahrlDotCom.cfn.yaml)"
