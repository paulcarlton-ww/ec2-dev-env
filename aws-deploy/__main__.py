import pulumi
from pulumi import Output, ResourceOptions
import pulumi_aws as aws
import server, networking, roles, ssm, kms
import string
import random
import os
from config import Config, get_config_value

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return str(''.join(random.choice(chars) for _ in range(size)))

stack = pulumi.get_stack()
config = pulumi.Config()
server_config = config.require_object("server")
app_config = config.require_object("application")
network_config = config.require_object("networking")
roles_config = config.require_object("role")
server_name = server_config.get("name") + "-" + id_generator()

try:
    debug_flag=os.getenv("EC2_DEBUG") is not None
    cfg = Config(debug_mode=debug_flag)

    ssh_access = get_config_value(cfg.server_config, "ssh_access", default="False")
    proxy_http=None
    proxy_https=None
    no_proxy=None
    proxy_port=None
    if server_config.get("proxy-setup") is not None:
        proxy_http=server_config["proxy-setup"].get("http-proxy")
        proxy_https=server_config["proxy-setup"].get("https-proxy")
        no_proxy=server_config["proxy-setup"].get("no-proxy")
        proxy_info = proxy_http.split(":")
        if len(proxy_info) == 3:
            proxy_port = proxy_info[2]

    az = network_config.get("az")
    if az is None:
        az = "a"

    region = network_config.get("region")
    if region is None:
        region = os.getenv("AWS_REGION")
    
    if region is None:
        raise Exception("region is required")
    
    source_cdir_env = app_config.get("ec2-dev:source-cdir-env")
    if source_cdir_env is None:
        source_cdir_env = "EC2_SOURCE_CDIR"
    source_cdir = os.getenv(source_cdir_env)
    if source_cdir is None:
        raise Exception("Environmental variable containing source cdir is required")

    networking = networking.NetworkingComponent(
        "networking",
        networking.NetworkingComponentArgs(
            prefix=server_name,
            cidr_block=network_config.get("vpc-cidr"),
            vpc_id=network_config.get("vpc-id"),
            public_subnet_cidr_block=network_config.get("public-subnet-cidr"),
            private_subnet_cidr_block=network_config.get("private-subnet-cidr"),
            public_subnet_id=network_config.get("public-subnet-id"),
            private_subnet_id=network_config.get("private-subnet-id"),
            ssh_access=ssh_access,
            proxy_port=proxy_port,
            az=az,
            region=region,
            source_cidr=source_cdir
        ),
    )

    config_bucket = aws.s3.Bucket(
        "configuration-bucket",
        acl="private",
        tags={
            "Environment": stack,
            "Name": server_name,
        },
    )

    s3_vpc_endpoint = roles_config.get("s3-vpc-endpoint")
    if s3_vpc_endpoint:
        s3_policy_yml = Output.all(config_bucket.id).apply(lambda l: f'''
AWSTemplateFormatVersion: "2010-09-09"
Description: S3 Bucket
Resources:
  UpdateS3VPCEndpoint:
    Type: Custom::VpcEndpointUpdater
    Properties:
      ServiceToken: !ImportValue VpcEndpointUpdaterARN
      VpcEndpointId: !ImportValue {s3_vpc_endpoint}
      Principal: "*"
      Action: "s3:*"
      Effect: "Allow"
      Resource:
        - "arn:aws:s3:::{l[0]}"
        - "arn:aws:s3:::{l[0]}/*"
''')

        s3_policy = aws.cloudformation.Stack(f"{server_name}s3-policy-config", template_body=s3_policy_yml, opts=ResourceOptions(depends_on=[config_bucket]), capabilities=["CAPABILITY_AUTO_EXPAND"])
    else:
        s3_policy = None

    github_token_env = app_config.get("ec2-dev:github-token-env")
    if github_token_env is None:
        github_token_env = "EC2_CI_GITHUB_TOKEN"
    github_token = os.getenv(github_token_env)
    if github_token is None:
        raise Exception("Environmental variable containing GitHub token is required")

    deployerFileName = "./deployer.sh"
    deployerFile = pulumi.FileAsset(deployerFileName)

    deployer_bucket_object = aws.s3.BucketObject(
        "deployer-key-object", bucket=config_bucket.id, source=deployerFile
    )
    
    permissions_boundary_arn = None
    iam_role = None
    if roles_config:
        permissions_boundary_arn = roles_config.get("permissions-boundary")
        policies = roles_config.get("policies")
        iam_role_name = roles_config.get("iam-role-name")
    
    if iam_role_name is None:
        roles = roles.RolesComponent(
            "roles",
            roles.RolesComponentArgs(
                config_bucket, policies, permissions_boundary_arn=permissions_boundary_arn
            ),
        )
        iam_role = roles.base_instance_role
    else:
        role_info = aws.iam.get_role(name=iam_role_name)
        iam_role = aws.iam.Role.get("iam_role", role_info.id)

    ssm_key = kms.KmsKeyComponent(
        "ssm-kms-key",
        cfg,
        description="used to encrypt ssm parameters",
        roles_actions={
            iam_role: [
                "kms:Decrypt",
                "kms:Encrypt",
                "kms:DescribeKey"
            ]
        },
        opts=pulumi.ResourceOptions(depends_on=[iam_role])
    )

    ssm.SsmParamComponent("github-token", github_token, cfg, val_type="SecureString", kms_key=ssm_key)

    ssm.SsmParamComponent("source-cidr", source_cdir, cfg)
    
    server_args = {
        "private_subnet": networking.private_subnet,
        "vpc_security_group_ids": [networking.tm_sg.id],
        "ami_id": server_config.get("ami-id"),
        "iam_role": iam_role,
        "ssh_key_name": server_config.get("ssh-key-name"),
        "private_ips": [server_config.get("ip-address")],
        "proxy_http": proxy_http,
        "proxy_https": proxy_https,
        "no_proxy": no_proxy,
        "stack_name": stack,
        "debug": debug_flag,
        "tags": {
            "Name": server_name,
            "Type": "ec2-dev"
        },
        "region": region,
        "ssh_access": ssh_access,
    }

    depends_on = []
    if s3_policy is not None:
        depends_on.append(s3_policy)    
    server_args["depends_on"] = depends_on

    root_volume_size = server_config.get("root-vol-size")
    if root_volume_size is not None:
        server_args["root_volume_size"] = root_volume_size

    root_volume_type = server_config.get("root-vol-type")
    if root_volume_type is not None:
        server_args["root_volume_type"] = root_volume_type

    instance_type = server_config.get("instance-type")
    if instance_type is not None:
        server_args["instance_type"] = instance_type

    user_data_file = app_config.get("user-data-file")
    if user_data_file is not None:
        server_args["user_data_file"] = user_data_file

    server = server.ServerComponent(server_name, **server_args)

    pulumi.export('instance', server.instance.id)
    
    deployer = aws.ssm.Document(f"{cfg.stack}-deployer",
        content="""{
    "schemaVersion": "1.2",
    "description": "Deployer.",
    "runtimeConfig": {
        "aws:runShellScript": {
            "properties": [
            {
                "id": "0.aws:runShellScript",
                "runCommand": ["/usr/local/bin/run-deployer.sh"]
            }
            ]
        }
    }
}""",
        document_type="Command",
        tags={
                "Name": f"{cfg.stack}-deployer", 
                "Stack": f"{cfg.stack}"
            },
        opts=pulumi.ResourceOptions(delete_before_replace=True)
    )

    pulumi.export("Deploy GHE backup utils SSM command:", deployer.name)
    
except Exception as e:
    print(f"Failed, execption: {e}")
    os.exit(1)
