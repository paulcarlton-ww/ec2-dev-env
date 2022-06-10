#!/usr/bin/env bash

debug_opt=""
if [ "{debug}" == "True" ]; then
    set -x
    debug_opt="--debug"
fi

export HOME=/home/ec2-user

function SetAWSCreds () {{
    INSTANCE_ROLE=$(aws sts get-caller-identity | jq -r '."Arn"' | cut -f 2 -d/)
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    iam=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/$INSTANCE_ROLE)

    export AWS_ACCESS_KEY_ID=$(echo $iam | jq -r '."AccessKeyId"')
    export AWS_SECRET_ACCESS_KEY=$(echo $iam | jq -r '."SecretAccessKey"')
    export AWS_SESSION_TOKEN=$(echo $iam | jq -r '."Token"')
    export AWS_REGION=$(curl --silent http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r '."region"')
}}

function GetParamValue() {{
    local key="$1"
    if [ -z "$key" ]; then
        echo "ssm parameter key not provided"
        exit 1
    fi
    local value="$(aws ssm get-parameter --name  $key --region $AWS_REGION --with-decryption | jq -r '."Parameter"["Value"]')"
    echo $value
}}

Install () {{
    amazon-linux-extras install epel -y

    echo "Installing proxy"

    echo "{proxy_http}"
    echo "{proxy_https}"
    echo "{no_proxy}"

    mkdir -p /etc/ec2-dev

    if [ "{proxy_http}" != "None" ]; then
        export http_proxy="{proxy_http}"
        export HTTP_PROXY="{proxy_http}"
        echo "export HTTP_PROXY={proxy_http}" >> /etc/ec2-dev/env.sh
        echo "export http_proxy={proxy_http}" >> /etc/ec2-dev/env.sh
        echo "proxy={proxy_http}" >> /etc/yum.conf
    fi

    if [ "{proxy_https}" != "None" ]; then
        export https_proxy="{proxy_https}"
        export HTTPS_PROXY="{proxy_https}"
        echo "export HTTPS_PROXY={proxy_https}" >> /etc/ec2-dev/env.sh
        echo "export https_proxy={proxy_https}" >> /etc/ec2-dev/env.sh
        export curl_proxy_opt="--proxy $https_proxy"
        echo "export curl_proxy_opt=\"--proxy $https_proxy\"" >> /etc/ec2-dev/env.sh
    fi

    if [ "{no_proxy}" != "None" ]; then
        export no_proxy="{no_proxy}"
        export NO_PROXY="{no_proxy}"
        echo "export NO_PROXY={no_proxy}" >> /etc/ec2-dev/env.sh
        echo "export no_proxy={no_proxy}" >> /etc/ec2-dev/env.sh
    fi

    echo "Updating system packages & installing required utilities"
    yum-config-manager --enable epel
    yum update -y
    yum install -y jq curl unzip git git-lfs
    curl $curl_proxy_opt "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/linux_64bit/session-manager-plugin.rpm" -o "session-manager-plugin.rpm"
    sudo yum install -y session-manager-plugin.rpm

    echo "Installing AWS CLI"
    TMPDIR=$(mktemp -d)
    cd $TMPDIR
    echo "Downloading AWS CLI"
    curl $curl_proxy_opt "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip >/dev/null
    ./aws/install >/dev/null

    export AWS_REGION={region}
    SetAWSCreds

    echo "Installing SSM Agent"
    yum install -y https://s3.$AWS_REGION.amazonaws.com/amazon-ssm-$AWS_REGION/latest/linux_amd64/amazon-ssm-agent.rpm
    systemctl enable amazon-ssm-agent
    systemctl start amazon-ssm-agent
    systemctl status amazon-ssm-agent

    curl -o aws-iam-authenticator https://amazon-eks.s3-us-west-2.amazonaws.com/1.14.6/2019-08-22/bin/linux/amd64/aws-iam-authenticator
    chmod +x ./aws-iam-authenticator
    mkdir -p //bin && mv ./aws-iam-authenticator $HOME/bin/aws-iam-authenticator && export PATH=$HOME/bin:$PATH
    echo 'export PATH=$HOME/bin:$PATH' >> ~/.bashrc
    curl -LO "https://dl.k8s.io/release/v1.22.9/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl
    sudo yum install -y docker
    sudo usermod -a -G docker ec2-user
    id ec2-user
    sudo systemctl enable docker.service
    sudo systemctl start docker.service
    curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
    sudo mv /tmp/eksctl /usr/local/bin
    curl -s https://fluxcd.io/install.sh | sudo bash

    
}}

Install

echo "export INSTANCE_ROLE={instance_role}" >> /etc/ec2-dev/env.sh
echo "export AWS_REGION={region}" >> /etc/ec2-dev/env.sh

