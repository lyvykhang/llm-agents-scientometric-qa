"""Here we define the main tools of the system using Pydantic.

Updates to these definitions should also be reflected in the function descriptions provided to `planning.py`.
"""

from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class ArticleFacetSearchParams(BaseModel):
    """Aggregate information from articles to find top authors, institutions, countries, etc."""

    # publicationYear: Optional[List[str]] = Field(
    #     None,
    #     description="A list with a start year and an end year, to search for articles in a specific year range.",
    # )
    ### Other params should follow (removed for confidentiality reasons).

    pass


class ArticleSearchParams(BaseModel):
    """Searches for articles."""

    # publicationYear: Optional[List[str]] = Field(
    #     None,
    #     description="A list with a start year and an end year, to search for articles in a specific year range.",
    # )
    ### Other params should follow (removed for confidentiality reasons).

    pass


class ArticleFacetSearchParamsNaive(BaseModel):
    """Aggregate information from articles to find top authors, institutions, countries, etc."""

    # query: str = Field(
    #     ...,
    #     description="A Boolean logical query to perform a filtered article search. Possible filters are: ...",
    #     examples=[],
    # )
    ### Other params should follow (removed for confidentiality reasons).

    pass


class ArticleSearchParamsNaive(BaseModel):
    """Aggregate information from articles to find top authors, institutions, countries, etc."""

    # query: str = Field(
    #     ...,
    #     description="A Boolean logical query to perform a filtered article search. Possible filters are: ...",
    #     examples=[],
    # )
    ### Other params should follow (removed for confidentiality reasons).

    pass


TOOL_DESCRIPTIONS = {
    "article_search": ArticleSearchParams,
    "article_facet_search": ArticleFacetSearchParams,
}

TOOL_DESCRIPTIONS_NAIVE = {
    "article_search": ArticleSearchParamsNaive,
    "article_facet_search": ArticleFacetSearchParamsNaive,
}


def get_relevant_tool_desc(tool_name: str):
    """
    Select a single tool description, e.g. to not crowd the prompt with unnecessary tools for a given plan step.
    """
    assert tool_name in TOOL_DESCRIPTIONS.keys(), "Invalid tool name."
    return [TOOL_DESCRIPTIONS[tool_name]]
