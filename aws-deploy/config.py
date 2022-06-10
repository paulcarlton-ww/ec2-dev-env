import boto3
import pulumi
import json
from pulumi_aws import Provider as AwsProvider
import pulumi_aws as aws
from pygments import highlight, lexers, formatters

class Config:
    def __init__(self, debug_mode=False):
        self.config = pulumi.Config()
        self.debug_mode=debug_mode
        aws_config = pulumi.Config("aws")
        self.aws_region = aws_config.require("region")
        self.aws_profile = aws_config.require("profile")
        self.aws_account = get_account(self)

        self.app_config = self.config.require_object("application")
        self.network_config = self.config.require_object("networking")
        self.server_config = self.config.require_object("server")
        self.roles_config = self.config.get_object("roles")

        # Create an AWS provider.
        self.aws_provider = AwsProvider(resource_name="aws-provider", profile=self.aws_profile, region=self.aws_region)

        self.stack = pulumi.get_stack()
        self.project = pulumi.get_project()
        self.stack_prefix=f"{self.stack}-"
    
    def __str__(self) -> str:
        text = f"project:  {self.project}, stack: {self.stack}"
        text += f"aws: region: {self.aws_region}, profile: {self.aws_profile}\n"
        text += f"app config...\n{json_colour(json.dumps(self.app_config, indent=4))}\n"
        text += f"net config...\n{json_colour(json.dumps(self.network_config, indent=4))}\n"
        text += f"server config...\n{json_colour(json.dumps(self.server_config, indent=4))}\n"
        text += f"roles config...\n{json_colour(json.dumps(self.roles_config, indent=4))}\n"

        return text

def get_config_value(config, name, default=None):
    if name is None:
        return default
    value = config.get(name)
    if value is None:
        return default
    return value

def true_false_text(value, default="false"):
  if value is None:
    return default
  if value:
    return "true"
  return "false"

def json_colour(json_text):
    return highlight(json_text, lexers.JsonLexer(), formatters.TerminalFormatter())

def get_account(cfg: Config):
    client = boto3.client("sts", region_name=cfg.aws_region)
    return client.get_caller_identity()["Account"]

