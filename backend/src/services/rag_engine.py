"""RAG (Retrieval-Augmented Generation) engine for email question answering.

This module provides the main entry point for RAG queries, routing them to
specialized handlers based on query type.
"""
from typing import Dict, Optional
import logging

from .embedding_service import EmbeddingService
from ..storage.storage_interface import StorageBackend
from .llm_processor import LLMProcessor
from .context_builder import ContextBuilder
from .query_classifier import QueryClassifier
from .result_cache import get_result_cache
from ..utils.query_utils import extract_number_from_query
from .query_handlers import (
    ConversationHandler,
    AggregationHandler,
    SenderHandler,
    AttachmentHandler,
    ClassificationHandler,
    TemporalHandler,
    SemanticHandler,
    PreviousResultsHandler,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class RAGQueryEngine:
    """RAG engine for question-answering over emails.

    Routes queries to specialized handlers based on query type:
    - conversation: Greetings, help requests
    - aggregation: Statistics and counting
    - search-by-sender: Find emails from specific sender
    - search-by-attachment: Find emails with attachments
    - classification: Label-based queries
    - temporal: Time-based queries
    - filtered-temporal: Time + content filtered queries
    - semantic: Content-based vector search
    """

    def __init__(
        self,
        storage: StorageBackend,
        embedding_service: EmbeddingService,
        llm_processor: LLMProcessor,
        top_k: int = 10
    ):
        """Initialize RAG engine.

        Args:
            storage: Storage backend with vector search
            embedding_service: Service for generating embeddings
            llm_processor: LangChain-based LLM processor
            top_k: Number of similar emails to retrieve (default: 10)
        """
        self.storage = storage
        self.embedder = embedding_service
        self.llm = llm_processor
        self.top_k = top_k
        self.context_builder = ContextBuilder()

        # Initialize classifier
        self.classifier = QueryClassifier(llm_processor)

        # Initialize handlers
        self.handlers = self._create_handlers()

        logger.info(
            "[RAG INIT] Initialized RAG engine - LLM Provider: %s, Model: %s, Top-K: %s",
            llm_processor.provider,
            llm_processor.model,
            top_k,
        )

    def _create_handlers(self) -> Dict:
        """Create handler instances for each query type."""
        base_args = {
            'storage': self.storage,
            'llm': self.llm,
            'context_builder': self.context_builder,
        }

        return {
            'conversation': ConversationHandler(**base_args),
            'aggregation': AggregationHandler(**base_args),
            'search-by-sender': SenderHandler(**base_args),
            'search-by-attachment': AttachmentHandler(**base_args),
            'classification': ClassificationHandler(**base_args),
            'temporal': TemporalHandler(**base_args),
            'filtered-temporal': TemporalHandler(**base_args),
            'semantic': SemanticHandler(**base_args, embedder=self.embedder),
            'list-previous-results': PreviousResultsHandler(**base_args),
        }

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        similarity_threshold: float = 0.5,
        chat_history: Optional[list] = None,
        session_id: Optional[str] = None,
    ) -> Dict:
        """Answer a question based on email content.

        Args:
            question: User's question
            top_k: Number of emails to retrieve (uses default if None)
            similarity_threshold: Minimum similarity score (0.0-1.0)
            chat_history: Optional list of previous messages [{"role": "user/assistant", "content": "..."}]
            session_id: Optional session ID for result caching (enables follow-up queries)

        Returns:
            Dict with:
                - answer: The LLM's answer
                - sources: List of source emails with metadata
                - question: The original question
                - confidence: 'high', 'medium', 'low', or 'none'
                - query_type: The detected query type
                - cached_message_ids: List of message IDs (for caching, max 500)
        """
        # Extract number from query as fallback (LLM will override if it returns a count)
        extracted_limit = extract_number_from_query(question, default=self.top_k)
        chat_history = chat_history or []

        logger.info(f"[RAG QUERY] Processing question with {self.llm.provider}/{self.llm.model}")
        logger.info(
            f"[RAG QUERY] Question: '{question}', extracted_limit: {extracted_limit}, "
            f"threshold: {similarity_threshold}, session: {session_id}"
        )
        if chat_history:
            logger.info(f"[RAG QUERY] Using {len(chat_history)} previous messages for context")

        # Detect query type and desired count from LLM
        logger.info("[RAG QUERY] ========== Starting Query Classification ==========")
        query_type, llm_count = self.classifier.detect_query_type(question, chat_history)
        logger.info("[RAG QUERY] ========== Classification Complete ==========")
        logger.info(f"[RAG QUERY] Detected query type: {query_type}, LLM count: {llm_count}")

        # Use LLM-extracted count if available, otherwise use extracted_limit from regex fallback
        if llm_count is not None:
            extracted_limit = llm_count
            logger.info(f"[RAG QUERY] Using LLM-extracted count: {llm_count}")
        k = top_k if top_k is not None else extracted_limit
        logger.info(f"[RAG QUERY] Final limit k: {k} (top_k={top_k}, extracted_limit={extracted_limit})")

        # Get the appropriate handler
        handler = self.handlers.get(query_type)
        if not handler:
            logger.error(f"[RAG QUERY] No handler for query type: {query_type}")
            return {
                'answer': "I'm not sure how to handle that type of question.",
                'sources': [],
                'question': question,
                'confidence': 'none',
                'query_type': query_type,
                'total_count': None,
                'cached_message_ids': None,
            }

        # Route to handler
        logger.info("[RAG QUERY] ========== Routing to Handler ==========")
        logger.info(f"[RAG QUERY] Handler: {handler.__class__.__name__}")
        logger.info(f"[RAG QUERY] Parameters: limit={k}, threshold={similarity_threshold}")

        # Handle special cases for handlers with extra parameters
        if query_type == 'semantic':
            result = handler.handle(question, limit=k, threshold=similarity_threshold, chat_history=chat_history)
        elif query_type == 'filtered-temporal':
            result = handler.handle_filtered(question, limit=k, chat_history=chat_history)
        elif query_type == 'list-previous-results':
            result = handler.handle(question, limit=k, chat_history=chat_history, session_id=session_id)
        else:
            result = handler.handle(question, limit=k, chat_history=chat_history)

        # Cache result message IDs for follow-up queries
        if session_id:
            self._cache_result(session_id, result, question, query_type)

        return result

    def _cache_result(
        self,
        session_id: str,
        result: Dict,
        question: str,
        query_type: str,
    ) -> None:
        """Cache message IDs from query result for follow-up queries.

        Args:
            session_id: Chat session ID
            result: Query result dict
            question: Original question
            query_type: Type of query
        """
        # Skip caching for conversation queries (no email results)
        if query_type == 'conversation':
            return

        # Extract message IDs from sources
        sources = result.get('sources', [])
        if not sources:
            logger.debug("[RAG CACHE] No sources to cache for session %s", session_id)
            return

        # Use cached_message_ids if already set (e.g., from list_by_topic)
        message_ids = result.get('cached_message_ids')
        if not message_ids:
            message_ids = [s.get('message_id') for s in sources if s.get('message_id')]

        if message_ids:
            cache = get_result_cache()
            total_count = result.get('total_count')
            cache.store(
                session_id=session_id,
                message_ids=message_ids,
                query=question,
                query_type=query_type,
                total_count=total_count,
            )
            logger.info(
                "[RAG CACHE] Cached %d message IDs for session %s (total: %s)",
                len(message_ids), session_id, total_count
            )

    # Legacy method for backwards compatibility
    def _detect_query_type(self, question: str) -> str:
        """Detect query type - delegates to classifier.

        Kept for backwards compatibility.
        Returns only the query type (ignores count).
        """
        query_type, _ = self.classifier.detect_query_type(question)
        return query_type
