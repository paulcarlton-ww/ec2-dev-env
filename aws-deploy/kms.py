import pulumi_aws as aws
from config import Config
import pulumi
import json
from typing import Optional, Mapping, Sequence
import ssm


class KmsKeyComponent(pulumi.ComponentResource):
  cfg: Config
  name: str
  description: str
  roles_actions: Mapping[aws.iam.Role,Sequence[str]]

  def __init__(self,
    name: str,
    cfg: Config,
    description: Optional[str] = "",
    roles_actions: Optional[Mapping[aws.iam.Role,Sequence[str]]] = None,
    opts=None):
      super().__init__("pkg:index:KmsKeyComponent", name, None, opts)
      self.cfg = cfg
      self.description = description
      self.name = name
      self.roles_actions = roles_actions

      self.opts = pulumi.ResourceOptions(parent=self)
      if opts is not None:
        self.opts = opts
      if self.opts.parent is None:
        self.opts.parent = self

      key_name = f"{cfg.hcs_org}-{cfg.project}-{cfg.stack}-{name}"
      kwargs = {
        "tags": {
            "Name": f"{cfg.hcs_org}-{cfg.project}-{cfg.stack}-{name}", 
            "Stack": f"{cfg.stack}",
        },
        "deletion_window_in_days": 10,
        "description": f"{cfg.stack} {self.description}",
        "policy": self.set_policy(),
        "opts": self.opts
      }

      self.kms_key = aws.kms.Key(name, **kwargs)

      self.alias = aws.kms.Alias(
        key_name,
        name=f"alias/{key_name}",
        target_key_id=self.kms_key.id,
        opts=pulumi.ResourceOptions(parent=self, depends_on=self.kms_key)
      )
      
      pulumi.export(f"ssm params kms key name", self.alias.name)

      self.ssm_param = ssm.SsmParamComponent(
        "ssm-kms-key",
        self.kms_key.arn,
        self.cfg,
        opts=pulumi.ResourceOptions(
          parent=self,
          depends_on=[self.kms_key])
      )
  
  def set_policy(self):
    static_template = '''
{{
    "Version": "2008-10-17",
    "Statement": [
        {{
            "Sid": "Allow key administration to the Account.",
            "Effect": "Allow",
            "Principal": {{
                "AWS": "arn:aws:iam::{aws_account}:root"
            }},
            "Action": "kms:*",
            "Resource": "*"
        }}'''
  
    role_template =''',
        {{
            "Sid": "Allow the key to be used from {role_name}",
            "Effect": "Allow",
            "Principal": {{
                "AWS": ["{role_arn}"]
            }},
            "Action": {actions},
            "Resource": "*"
        }}'''

    tail = '''
    ]
}'''

    kwargs = {
      "aws_account": self.cfg.aws_account,
      "aws_region": self.cfg.aws_region
    }
    static_policy = static_template.format(**kwargs)
    policy = ""

    for role, actions in self.roles_actions.items():
      kwargs = {
        "role_name": role.name,
        "role_arn": role.arn,
        "actions": json.dumps(actions),
      }

      policy = pulumi.Output.concat(policy, pulumi.Output.all(**kwargs).apply(lambda kwargs: role_template.format(**kwargs)))

    return pulumi.Output.concat(static_policy, policy, tail)
