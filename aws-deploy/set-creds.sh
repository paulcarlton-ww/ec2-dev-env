#!/usr/bin/env bash
INSTANCE_ROLE=${INSTANCE_ROLE:-$(aws sts get-caller-identity | jq -r '."Arn"' | cut -f 2 -d/)}
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
iam=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/$INSTANCE_ROLE)

export AWS_ACCESS_KEY_ID=$(echo $iam | jq -r '."AccessKeyId"')
export AWS_SECRET_ACCESS_KEY=$(echo $iam | jq -r '."SecretAccessKey"')
export AWS_SESSION_TOKEN=$(echo $iam | jq -r '."Token"')
export AWS_REGION=$(curl --silent http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r '."region"')