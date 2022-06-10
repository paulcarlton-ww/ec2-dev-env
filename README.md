# Create EC2 Development Environment

This repository contains a python pulumi utility for creating and ec2 instance for use as a development environment

## Setup

Install python3, pip, [Pulumi](https://www.pulumi.com/docs/get-started/install/) and [AWS CLI version 2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2-mac.html).

Clone this repository and deploy the python code in a virtualenv, e.g.

    cd <path to clone of directory>
    export PATH=$PATH:$PWD/bin
    cd aws-deploy
    pip install virtualenv
    virtualenv venv
    source venv/bin/activate
    pip install -r requirements.txt

## Deploy

To deploy an ec2 instance you need AWS credentials for and Admin user in the target AWS account.

Create an S3 bucket to use for the pulumi stack:

    create-state-bucket.sh <bucket name> <AWS region> <stack name>

e.g.

    create-state-bucket.sh aws-instances $AWS_REGION ec2-dev-one

Then copy the sample yaml file to `Pulumi.<stack-name>.yaml and edit it to reflect the requirements for your instance, i.e.

    cd aws-deploy
    cp Pulumi.sample.yaml Pulumi.ec2-dev-one.yaml

When ready to create the test manager, source your AWS credentials for the target account and deploy the test manager:

    export PULUMI_CONFIG_PASSPHRASE=""    
    pulumi --non-interactive login s3://aws-instances
    pulumi --non-interactive up  --yes --stack ec2-dev-one

