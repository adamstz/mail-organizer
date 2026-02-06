"""Structured types for RAG query responses.

This module provides consistent, type-safe data structures for the RAG pipeline,
ensuring all handlers return the same response format.
"""
from typing import TypedDict, Literal, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# Type aliases for query classification and confidence levels
QueryType = Literal[
    'conversation',
    'aggregation',
    'search-by-sender',
    'search-by-attachment',
    'classification',
    'filtered-temporal',
    'temporal',
    'semantic',
    'list-previous-results',  # New: for follow-up list queries
]

Confidence = Literal['high', 'medium', 'low', 'none']


class SourceMetadata(TypedDict, total=False):
    """Metadata for a source email included in query results.

    All fields are optional to handle partial data gracefully.
    """
    message_id: str
    subject: Optional[str]
    from_: Optional[str]  # Note: 'from' is a reserved keyword
    snippet: Optional[str]
    similarity: float
    date: Optional[int]


class QueryResponse(BaseModel):
    """Standardized response from RAG query handlers.

    This model ensures all handlers return consistent data structures,
    enabling type-safe pipeline processing and proper caching.
    """
    model_config = ConfigDict(extra='forbid')  # Prevent arbitrary extra fields

    answer: str = Field(description="The LLM-generated answer to the query")
    sources: List[dict] = Field(
        default_factory=list,
        description="List of source email metadata used to generate the answer"
    )
    question: str = Field(description="The original user question")
    confidence: Confidence = Field(
        default='high',
        description="Confidence level of the response"
    )
    query_type: str = Field(description="The detected/handled query type")

    # Optional fields for specific handlers
    total_count: Optional[int] = Field(
        default=None,
        description="Total count for aggregation/classification queries"
    )

    # Caching support - stores message IDs for follow-up queries
    cached_message_ids: Optional[List[str]] = Field(
        default=None,
        description="Message IDs from this query result (max 500) for follow-up 'list those' queries"
    )


# Maximum number of message IDs to cache per query result
MAX_CACHED_IDS = 500
