"""Stores the LangChain prompt templates used to define agents.

The class AgentPromptTemplate is used to instantiate and store (additional) prompts for an agent. Note that the actual prompt literals are stored in `./config/<agent>.py`.
"""

from copy import deepcopy
from enum import Enum

from langchain_core.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from config.prompts.action import ACTION_AGENT_SYSTEM_PROMPT_V3
from config.prompts.high_level_planning import (
    HIGH_LEVEL_PLANNING_AGENT_SYSTEM_PROMPT_V3,
    HIGH_LEVEL_PLANNING_AGENT_USER_PROMPT_V3,
)
from config.prompts.planning import (
    PLANNING_AGENT_CONTEXT_PROMPT_V3,
    PLANNING_AGENT_SYSTEM_PROMPT_V3,
    PLANNING_AGENT_USER_PROMPT_V3,
)
from config.prompts.writing import WRITING_AGENT_SYSTEM_PROMPT_V3


class Agent(Enum):
    HIGH_LEVEL_PLANNING_AGENT = "high_level_planning_agent"
    PLANNING_AGENT = "planning_agent"
    ACTION_AGENT = "action_agent"
    WRITING_AGENT = "writing_agent"


agent_templates = {
    Agent.HIGH_LEVEL_PLANNING_AGENT: {
        "default_version": "3.1",
        "versions": {
            "3.1": {
                "messages": [
                    SystemMessagePromptTemplate.from_template(
                        HIGH_LEVEL_PLANNING_AGENT_SYSTEM_PROMPT_V3
                    ),
                    HumanMessagePromptTemplate.from_template(
                        HIGH_LEVEL_PLANNING_AGENT_USER_PROMPT_V3,
                        input_variables=["query"],
                    ),
                ]
            }
        },
    },
    Agent.PLANNING_AGENT: {
        "default_version": "3.1",
        "versions": {
            "3.1": {
                "messages": [
                    SystemMessagePromptTemplate.from_template(
                        PLANNING_AGENT_SYSTEM_PROMPT_V3
                    ),
                    HumanMessagePromptTemplate.from_template(
                        PLANNING_AGENT_CONTEXT_PROMPT_V3,
                        input_variables=["high_level_steps", "entity_ids"],
                    ),
                    HumanMessagePromptTemplate.from_template(
                        PLANNING_AGENT_USER_PROMPT_V3,
                        input_variables=["user_query_message"],
                    ),
                ]
            }
        },
    },
    Agent.ACTION_AGENT: {
        "default_version": "3.1",
        "versions": {
            "3.1": {
                "messages": [
                    SystemMessagePromptTemplate.from_template(
                        ACTION_AGENT_SYSTEM_PROMPT_V3
                    )
                ]
            }
        },
    },
    Agent.WRITING_AGENT: {
        "default_version": "3.1",
        "versions": {
            "3.1": {
                "messages": [
                    SystemMessagePromptTemplate.from_template(
                        WRITING_AGENT_SYSTEM_PROMPT_V3
                    ),
                ]
            }
        },
    },
}


class AgentPromptTemplate:
    def __init__(self, agent: Agent, prompt_version: str = None):
        self.agent = agent
        self.prompt_version = (
            prompt_version
            if prompt_version
            else agent_templates[agent].get("default_version")
        )
        self.templates = deepcopy(
            agent_templates[agent]["versions"][prompt_version].get("messages", [])
        )

    def add_user_template(self, template: str, input_variables=None):
        if input_variables is None:
            input_variables = []
        user_template = HumanMessagePromptTemplate.from_template(
            template=f"""{template}""", input_variables=input_variables
        )
        self.templates.append(user_template)

    def add_ai_template(self, template: str, input_variables=None):
        if input_variables is None:
            input_variables = []
        ai_template = AIMessagePromptTemplate.from_template(
            template=f"""{template}""", input_variables=input_variables
        )
        self.templates.append(ai_template)

    def get_prompt_template(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(self.templates)
