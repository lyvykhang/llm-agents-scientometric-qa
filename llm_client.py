import os
from enum import Enum

from langchain_openai import AzureChatOpenAI


class deploymentNames(Enum):
    GPT_4O = "gpt4o-240513"
    GPT_4O_MINI = "gpt4o-mini-240718"
    GPT_O1_MINI = "o1-mini"


def yield_llm_client(
    azure_deployment: str,
    azure_endpoint: str = os.getenv("AZURE_OPENAI_URL_BASE"),
    api_key: str = os.getenv("OPENAI_ORGANIZATION_KEY"),
    api_version: str = os.getenv("AZURE_OPENAI_API_VERSION"),
    **kwargs,
) -> AzureChatOpenAI:
    """
    Return a chat model for requests.
    """
    return AzureChatOpenAI(
        azure_deployment=azure_deployment,
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version,
        **kwargs,
    )
