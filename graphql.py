"""Provides entity resolution functionality using the GraphQL endpoint.

GQLEntityResolver contains a main method `resolve()`, which takes a single reference to an entity and its type (ID or natural language query, e.g. "Harvard University") and maps it to the other reference (ID -> name or name -> ID).
"""

import json
from typing import Literal
import warnings

import requests


class GraphQLRetrievalException(Exception):
    pass


class GQLEntityResolver:
    def __init__(self):
        pass

    @classmethod
    def resolve(
        self,
        entity_reference: str,
        type_: str,
    ) -> list[dict]:
        pass
