"""Defines the workflow of the system.

Defines a BasePipeline class, which contains a method `run_conversation`, used for single conversations (one question-answer pair), i.e. one "run" of the system, as well as methods for supplying additional arguments to each agent. Executes agents (and any tool calls) in order, with naive parallelism.
"""

import json
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from traceback import format_exc
from types import ModuleType

import json_repair
from langchain_core.messages import HumanMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
)

import tools_api
from agents import (
    ActionAgentV3,
    BaseAgentV3,
    HighLevelPlanningAgentV3,
    PlanningAgentV3,
    PlanStep,
    WritingAgentV3,
)
from config.prompts.naive import NAIVE_NER_PROMPT
from config.prompts.tools import TOOL_DESCRIPTIONS, TOOL_DESCRIPTIONS_NAIVE
from config.prompts.writing import WRITING_AGENT_SYSTEM_PROMPT_V3
from graphql import GQLEntityResolver
from llm_client import deploymentNames
from logger.logger import logging_decorator


class pipeKwargGroups(Enum):
    PLANNING = "planning_params"
    ACTION = "action_params"
    WRITING = "writing_params"


class BasePipeline(ABC):
    def __init__(self, tool_module: ModuleType):
        self.tool_module = tool_module
        self.conversation_kwargs = {
            pipeKwargGroups.PLANNING.value: {},
            pipeKwargGroups.ACTION.value: {},
            pipeKwargGroups.WRITING.value: {},
        }
        self.context = None
        self.plan = None
        self.tools_responses = None
        self.final_response = None

    def __str__(self):
        s = ""
        for out in (
            json.dumps(self.context, indent=2),
            self.plan,
            self.tools_responses,
            self.final_response,
        ):
            s += "*=============================\n"
            if isinstance(out, list):
                for msg in out:
                    s += f"{msg.content}\n"
            else:
                s += f"{out}\n"
        return s

    def add_kwargs_to_dict(self, group_name: pipeKwargGroups, **kwargs):
        self.conversation_kwargs[group_name.value] = kwargs

    def list_kwargs(self):
        for kwargs in self.conversation_kwargs:
            print(
                "\tkwarg group `{}`: {}".format(
                    kwargs, self.conversation_kwargs[kwargs]
                )
            )
        print()

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def run_conversation(self, query: str):
        """
        Run the main workflow, i.e. (context) -> planning -> step execution -> final response composition and self-assign results to facilitate logging. This general workflow should be preserved across all pipeline implementations.
        """
        self.context, _ = self._conversation_context(query=query)
        self.list_kwargs()
        self.plan = self._run_planning_agent(
            query=query, **self.conversation_kwargs[pipeKwargGroups.PLANNING.value]
        )
        self.tools_responses = self._run_plan_steps_parallel(
            plan_str=self.plan, **self.conversation_kwargs[pipeKwargGroups.ACTION.value]
        )
        self.final_response = self._run_writing_agent(
            query=query,
            data=self.tools_responses,
            **self.conversation_kwargs[pipeKwargGroups.WRITING.value],
        )

    @abstractmethod
    def _conversation_context(self, query: str):
        """
        For providing optional context to the planning agent prior to `run_conversation`, e.g. a high-level planner or entity lookup step. The output of this should be provided as input to `self.run_planning_agent`.
        """
        pass

    @abstractmethod
    def _run_planning_agent(self, query: str):
        """
        Invoke the planning agent.
        """
        pass

    @abstractmethod
    def _run_action_agent(self, step: PlanStep) -> list:
        """
        Invoke the action agent on a single step.
        """
        pass

    @abstractmethod
    def _run_writing_agent(self, query: str, data: list):
        """
        Invoke the final writing agent.
        """
        pass

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _run_plan_steps_parallel(self, plan_str: str):
        """
        Receives the planning agent output and processes the steps, in parallel where possible. Implicitly assumes that *in*dependent tasks will always precede dependent tasks. Executes *all* parallel tasks before moving on to tasks with dependencies. The action agent is bypassed if the step being executed is independent.
        """
        plan = list(PlanStep.plan_step_iterator(plan_str, self.tool_module))

        def wrapper(step: PlanStep, tools_responses: list):
            """
            Wrapper around `self._run_plan_step` for use with executor.
            """
            # Call action agent if step has dependencies.
            tool_calls = (
                self._run_action_agent(step, tools_responses)
                if len(step.dependencies) > 0
                else None
            )
            tools_responses = self._run_plan_step(step, tools_responses, tool_calls)
            return tools_responses

        # Execute parallel steps (if any).
        parallel_steps = [step for step in plan if not step.dependencies]
        tools_responses = []
        if len(parallel_steps) > 1:
            with ThreadPoolExecutor(max_workers=len(parallel_steps)) as executor:
                for response in executor.map(
                    wrapper, parallel_steps, [[] for _ in range(len(parallel_steps))]
                ):
                    tools_responses.extend(response)
        else:
            parallel_steps = []
        # Execute (remaining) sequential steps.
        for step in plan:
            if not step.executed:
                tools_responses = wrapper(step, tools_responses)
        return tools_responses

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _run_plan_step(
        self, step: PlanStep, tools_responses: list, tool_calls: list = None
    ):
        """
        Execute LLM-outputted tool call(s) (if any) with optional preprocessing, or call the function directly for a given plan step (if no tool call is present).
        """

        def invoke_requested_function(kwargs: dict):
            """
            Make the actual function call with specified arguments and collect response. Assumes that any and all tools take a single param. dict as input.
            """

            try:
                function_response = step.tool(**kwargs)
            except Exception:
                print(format_exc())
                function_response = {}
            function_args_out = {"tool": step.tool.__name__, "question": step.question}
            # Format function results.
            function_args_out.update(kwargs)
            response_entry = HumanMessage(
                content=f"""{{"{step.name}_arguments": {json.dumps(function_args_out)}, "{step.name}_results": {json.dumps(function_response)}}}"""
            )
            return response_entry

        if (tool_calls is not None) & (tool_calls != []):
            if len(tool_calls) > 1:  # Multiple tool calls requested.
                kwargs = [
                    self._parse_llm_tool_calls(tool_call["args"])
                    for tool_call in tool_calls
                ]
                with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
                    for response_entry in executor.map(
                        invoke_requested_function, kwargs
                    ):
                        if response_entry is not None:
                            tools_responses.append(response_entry)
            else:  # Single tool call requested.
                kwargs = self._parse_llm_tool_calls(tool_calls[0]["args"])
                response_entry = invoke_requested_function(kwargs)
                if response_entry is not None:
                    tools_responses.append(response_entry)
        else:  # No tool calls supplied.
            kwargs = self._parse_llm_tool_calls(step.parameters)
            response_entry = invoke_requested_function(kwargs)
            if response_entry is not None:
                tools_responses.append(response_entry)
        step.executed = True
        return tools_responses

    @abstractmethod
    def _parse_llm_tool_calls(self, llm_output_args: str):
        """
        Optional preprocessing function for formatting LLM-outputted tool calls, e.g. action agent tool calls.
        """
        pass


class PipelineV3(BasePipeline):
    def __init__(self):
        super().__init__(tool_module=tools_api)

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _conversation_context(self, query: str):
        context = HighLevelPlanningAgentV3(query=query).execute()
        context = json_repair.loads(context)
        # Resolve the identified entities.
        if "named_entities" not in context.keys():
            # In case high level planning agent leaves out these fields entirely instead of using a blank list.
            context["named_entities"] = []
            context["entity_types"] = []
        n_entities = len(context["named_entities"])
        resolver = GQLEntityResolver()
        entity_ids = []
        if n_entities > 1:
            with ThreadPoolExecutor(max_workers=min(3, n_entities)) as executor:
                args = [context["named_entities"], context["entity_types"]]
                for response in executor.map(resolver.resolve, *args):
                    entity_ids.extend(response)
        else:
            try:
                entity_ids.extend(
                    resolver.resolve(
                        context["named_entities"][0], context["entity_types"][0]
                    )
                )
            except IndexError:
                pass
        # Add high-level steps and list of entity IDs to planning agent input.
        self.add_kwargs_to_dict(
            pipeKwargGroups.PLANNING,
            high_level_steps=context["high_level_steps"],
            entity_ids=entity_ids,
        )
        return context, entity_ids

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _run_planning_agent(
        self, query: str, high_level_steps: list[str], entity_ids: list[dict]
    ):
        return PlanningAgentV3(
            query=query, high_level_steps=high_level_steps, entity_ids=entity_ids
        ).execute()

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _run_action_agent(self, step: PlanStep, tools_responses: list = []):
        return ActionAgentV3(plan_step=step, tools_responses=tools_responses).execute()

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _run_writing_agent(self, query: str, data: list[str]):
        return WritingAgentV3(
            query=query,
            data=data,
        ).execute()

    def _parse_llm_tool_calls(self, llm_output_args):
        return {"parameters": llm_output_args}


class PipelineNaive:
    """
    The baseline first performs NER (otherwise it would be totally unable to answer any queries), then directly moves on to tool selection, tool execution (with/without manual query building), and final response composition. By nature, it is not able to answer multiple-intent or nested queries.
    """

    def __init__(self, tool_module: ModuleType, naive_query_building: bool):
        self.tool_module = tool_module
        self.naive_query_building = naive_query_building
        self.tagged_entities = None
        self.tools_responses = None
        self.final_response = None

    def __str__(self):
        s = ""
        for out in (
            json.dumps(self.tagged_entities, indent=2),
            self.tools_responses,
            self.final_response,
        ):
            s += "*=============================\n"
            if isinstance(out, list):
                for msg in out:
                    s += f"{msg.content}\n"
            else:
                s += f"{out}\n"
        return s

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def run_conversation(self, query: str):
        self.tagged_entities, entity_ids = self._lookup_entities(query)
        tool_calls = self._tool_selection(query, entity_ids)
        self.tools_responses = self._run_tool_calls(tool_calls)
        self.final_response = self._write_final_response(query, self.tools_responses)

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _lookup_entities(self, query: str):
        prompt = ChatPromptTemplate.from_messages(
            [SystemMessagePromptTemplate.from_template(NAIVE_NER_PROMPT)]
        ) + [BaseAgentV3.get_user_template(query)]
        messages = prompt.format_messages()
        response = BaseAgentV3.send_llm_request(
            messages=messages,
            model=deploymentNames.GPT_4O_MINI.value,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        response = json_repair.loads(response)
        n_entities = len(response["named_entities"])
        resolver = GQLEntityResolver()
        entity_ids = []
        if n_entities > 1:
            with ThreadPoolExecutor(max_workers=min(3, n_entities)) as executor:
                args = [response["named_entities"], response["entity_types"]]
                for result in executor.map(resolver.resolve, *args):
                    entity_ids.extend(result)
        else:
            try:
                entity_ids.extend(
                    resolver.resolve(
                        response["named_entities"][0], response["entity_types"][0]
                    )
                )
            except IndexError:
                pass
        return response, entity_ids

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _tool_selection(self, query: str, entity_ids: list):
        messages = [
            HumanMessage(content=query),
            HumanMessage(content=json.dumps(entity_ids)),
        ]
        tool_descs = (
            TOOL_DESCRIPTIONS_NAIVE if self.naive_query_building else TOOL_DESCRIPTIONS
        )
        tool_calls = BaseAgentV3.send_llm_request(
            messages=messages,
            model=deploymentNames.GPT_4O_MINI.value,
            tools=list(tool_descs.values()),
        )
        return tool_calls

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _run_tool_calls(self, tool_calls: list[dict]):
        def invoke_requested_function(tool_call: dict):
            """
            Make the actual function call with specified arguments and collect response. Assumes that any and all tools take a single param. dict as input.
            """
            tool_descs = (
                TOOL_DESCRIPTIONS_NAIVE
                if self.naive_query_building
                else TOOL_DESCRIPTIONS
            )
            tool_name_map = {v.__name__: k for k, v in tool_descs.items()}
            tool = getattr(self.tool_module, tool_name_map[tool_call["name"]])
            try:
                function_response = tool(tool_call["args"])
            except Exception:
                print(format_exc())
                function_response = {}
            function_args_out = {"tool": tool.__name__}
            # Format function results.
            function_args_out.update(tool_call["args"])
            response_entry = HumanMessage(
                content=f"""{{"{tool_call["id"]}_arguments": {json.dumps(function_args_out)}, "{tool_call["id"]}_results": {json.dumps(function_response)}}}"""
            )
            return response_entry

        tools_responses = []
        if tool_calls:
            if len(tool_calls) > 1:  # Multiple tool calls requested.
                with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
                    for response_entry in executor.map(
                        invoke_requested_function, tool_calls
                    ):
                        if response_entry is not None:
                            tools_responses.append(response_entry)
            else:  # Single tool call requested.
                response_entry = invoke_requested_function(tool_calls[0])
                if response_entry is not None:
                    tools_responses.append(response_entry)
        return tools_responses

    @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True)
    def _write_final_response(self, query: str, tools_responses: list):
        prompt = (
            ChatPromptTemplate.from_messages(
                [
                    SystemMessagePromptTemplate.from_template(
                        WRITING_AGENT_SYSTEM_PROMPT_V3
                    )
                ]
            )
            + [BaseAgentV3.get_user_template(query)]
            + ChatPromptTemplate.from_messages(tools_responses)
        )
        messages = prompt.format_messages()
        response = BaseAgentV3.send_llm_request(
            messages=messages, model=deploymentNames.GPT_4O_MINI.value, max_tokens=2000
        )
        return response
