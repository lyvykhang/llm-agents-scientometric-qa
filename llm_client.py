import os
import subprocess
from enum import Enum

import boto3
from botocore.exceptions import (
    NoCredentialsError,
    PartialCredentialsError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)
from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_openai import AzureChatOpenAI

load_dotenv()


class deploymentNames(Enum):
    GPT_4O = "gpt4o-240513"
    GPT_4O_MINI = "gpt4o-mini-240718"
    GPT_41_MINI = "gpt-4.1-mini"
    GPT_O1_MINI = "o1-mini"


class deploymentNamesBedrock(Enum):
    CLAUDE_35_SONNET = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    CLAUDE_3_HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"
    CLAUDE_35_HAIKU = "anthropic.claude-3-5-haiku-20241022-v1:0"  # us-west-2 only.


def aws_sso_refresh(aws_profile_name: str):
    try:
        dev = boto3.Session(profile_name=aws_profile_name)
        sts_client = dev.client("sts")
        sts_client.get_caller_identity()
    except (
        NoCredentialsError,
        PartialCredentialsError,
        UnauthorizedSSOTokenError,
        TokenRetrievalError,
    ):
        print("SSO login is invalid or expired. (Re-)authorizing...")
        subprocess.run(
            ["aws", "sso", "login", "--profile", aws_profile_name], check=True
        )
    return


def yield_llm_client(
    deployment_name: str,
    aws_profile_name: str = None,
    aws_region_name: str = "us-east-1",
    aws_sso_check: bool = True,
    azure_endpoint: str = os.getenv("AZURE_OPENAI_URL_BASE"),
    api_key: str = os.getenv("OPENAI_ORGANIZATION_KEY"),
    api_version: str = os.getenv("AZURE_OPENAI_API_VERSION"),
    **kwargs,
) -> AzureChatOpenAI | ChatBedrockConverse:
    """
    Return a chat model for requests.
    """
    if deployment_name in deploymentNamesBedrock._value2member_map_.keys():
        assert aws_profile_name is not None, (
            "aws_profile_name must be provided for Bedrock models."
        )
        if aws_sso_check:
            aws_sso_refresh(aws_profile_name)
        return ChatBedrockConverse(
            model=deployment_name,
            region_name=aws_region_name,
            credentials_profile_name=aws_profile_name,
            **kwargs,
        )
    elif deployment_name in deploymentNames._value2member_map_.keys():
        return AzureChatOpenAI(
            azure_deployment=deployment_name,
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version,
            **kwargs,
        )
    else:
        raise ValueError("Error: Unsupported deployment name.")
