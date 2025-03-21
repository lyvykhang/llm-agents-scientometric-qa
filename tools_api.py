"""Defines classes for working with API tool calls.

ArticleSearch, ArticleFacetSearch, and AuthorSearch are concrete implementations of the abstract class APIToolCall, which contain methods for manual assembly of a query from (LLM-outputted) parameters, preparing and sending the request to the DB, and processing the response. There are also wrapper functions that instantiate and call the main method of these classes, e.g. article_search.
"""

import json
from abc import ABC, abstractmethod
from typing import Literal

import json_repair
import requests

from graphql import GQLEntityResolver


class APIToolCall(ABC):
    def __init__(
        self,
        url: str,
        parameters: dict[str],
        search_entity: Literal["article", "author"],
    ):
        self.url = url
        self.parameters = parameters
        self.search_entity = search_entity
        self.query_is_llm_generated = None

    @classmethod
    def _build_db_query(self) -> str:
        """
        Assemble the model-outputted param. list into a syntactically-correct database query. Optional step, skipped if "query" is present in `self.parameters`.
        """
        pass

    @abstractmethod
    def _set_payload_params(self, query: str):
        pass

    @classmethod
    def _send_request(self, payload: str) -> requests.Response:
        return requests.request(
            "POST", self.url, headers={"Content-Type": "application/json"}, data=payload
        )

    @abstractmethod
    def _postprocess_response(self, response: requests.Response):
        pass

    def get_results_from_db(self) -> dict[str]:
        if "query" not in self.parameters.keys():
            q = self._build_db_query()
            self.query_is_llm_generated = False
        else:
            q = self.parameters["query"]
            self.query_is_llm_generated = True
        payload = self._set_payload_params(q)
        response = self._send_request(payload)
        return self._postprocess_response(response)


class ArticleFacetSearch(APIToolCall):
    def __init__(self, parameters):
        super().__init__(
            url="",
            parameters=parameters,
            search_entity="article",
        )

    def _set_payload_params(self, query):
        pass

    def _postprocess_response(self, response):
        pass


class ArticleSearch(APIToolCall):
    def __init__(self, parameters):
        super().__init__(
            url="",
            parameters=parameters,
            search_entity="article",
        )

    def _set_payload_params(self, query):
        pass

    def _postprocess_response(self, response):
        pass


class AuthorSearch(APIToolCall):
    def __init__(self, parameters):
        super().__init__(
            url="",
            parameters=parameters,
            search_entity="author",
        )
    
    def _set_payload_params(self, query):
        pass

    def _postprocess_response(self, response):
        pass


def article_facet_search(parameters: dict[str]):
    return ArticleFacetSearch(parameters).get_results_from_db()


def article_search(parameters: dict[str]):
    return ArticleSearch(parameters).get_results_from_db()


def author_search(parameters: dict[str]):
    return AuthorSearch(parameters).get_results_from_db()
