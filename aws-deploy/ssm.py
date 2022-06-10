import boto3
import json
import pulumi
from pulumi_aws import ssm, kms
from config import Config
from typing import Optional


class SsmParamComponent(pulumi.ComponentResource):
    cfg: Config
    ssm_param: ssm.Parameter
    name: str
    value: str
    val_type: str
    kms_key: kms.Key
    opts: pulumi.ResourceOptions

    def __init__(self,
      name: str, 
      value: str,
      cfg: Config,
      val_type: Optional[str]="String", 
      kms_key: Optional[kms.Key]=None,
      opts: pulumi.ResourceOptions=None):
        super().__init__("pkg:index:SsmParamComponent", name, None, opts)
        self.cfg = cfg
        self.value = value
        self.val_type = val_type
        self.kms_key = kms_key

        self.opts = pulumi.ResourceOptions(parent=self)
        if opts is not None:
          self.opts = opts
        if self.opts.parent is None:
          self.opts.parent = self
        
        ssm_param_name = f"/{cfg.hcs_org}/{cfg.project}/{cfg.stack}/{name}"
        kwargs = {
            "name": ssm_param_name,
            "type": self.val_type,
            "value": self.value,
            "tags": {
                "Name": f"{cfg.hcs_org}-{cfg.project}-{cfg.stack}-{name}", 
                "Stack": f"{cfg.stack}",
            },
            "opts": self.opts
        }
        if self.val_type == "SecureString":
            kwargs["key_id"] = self.kms_key.id
        
        self.ssm_param = ssm.Parameter(ssm_param_name, **kwargs)
        
        if self.val_type != "SecureString":
          pulumi.export(f"{ssm_param_name}", pulumi.Output.unsecret(self.ssm_param.value))

def get_value(cfg: Config, name: str) -> str:
  client = boto3.client('ssm', region_name=cfg.aws_region)
  ssm_param_name = f"/{cfg.hcs_org}/{cfg.project}/{cfg.stack}/{name}"

  try:
    response = client.get_parameter(Name=ssm_param_name, WithDecryption=True)
  except client.exceptions.ParameterNotFound:
    return None

  return response['Parameter']['Value']
