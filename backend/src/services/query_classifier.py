"""Query classifier for routing queries to appropriate handlers."""
import logging
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage

from .llm_processor import LLMProcessor
from .prompt_templates import QUERY_CLASSIFICATION_PROMPT
from ..classification_labels import is_classification_query

logger = logging.getLogger(__name__)


class QueryClassifier:
    """Classifies user queries to determine the appropriate handler.

    Uses LLM-based classification with fallback heuristics.
    """

    VALID_TYPES = {
        'conversation', 'aggregation', 'search-by-sender', 'search-by-attachment',
        'classification', 'filtered-temporal', 'temporal', 'semantic',
        'list-previous-results'  # For follow-up queries referencing previous results
    }

    # Patterns that indicate user wants to list/show previous results
    LIST_PREVIOUS_PATTERNS = [
        'list those', 'show those', 'show them', 'list them',
        'what are those', 'what are they', 'show me those',
        'list the', 'show the', 'display those', 'display them',
        'can you list', 'can you show', 'give me those',
        'what were those', 'what were they'
    ]

    def __init__(self, llm: LLMProcessor):
        """Initialize the classifier.

        Args:
            llm: LLM processor for classification
        """
        self.llm = llm

    def detect_query_type(self, question: str, chat_history: Optional[list] = None) -> str:
        """Detect the query type using LLM classification.

        Args:
            question: User's question
            chat_history: Optional list of previous messages for context

        Returns:
            One of: 'conversation', 'aggregation', 'search-by-sender',
                   'search-by-attachment', 'classification', 'filtered-temporal',
                   'temporal', 'semantic'
        """
        logger.info("[QUERY CLASSIFIER] ========== Starting query classification ==========")
        logger.info("[QUERY CLASSIFIER] Question: '%s'", question)
        logger.info("[QUERY CLASSIFIER] Chat history length: %d", len(chat_history) if chat_history else 0)

        # Check if this is a classification query using centralized module first
        if is_classification_query(question):
            logger.info("[QUERY CLASSIFIER] ✓ Detected as 'classification' via is_classification_query()")
            return 'classification'

        # Check if this is a follow-up query asking to list previous results
        if self._is_list_previous_request(question, chat_history):
            logger.info("[QUERY CLASSIFIER] ✓ Detected as 'list-previous-results' (follow-up list request)")
            return 'list-previous-results'

        # Use LLM to intelligently classify the query type
        # LLM now handles chat history context internally
        logger.info("[QUERY CLASSIFIER] Using LLM to classify query type")

        try:
            # Build chat context string for the prompt
            chat_context = ""
            if chat_history and len(chat_history) >= 2:
                recent_messages = chat_history[-4:]  # Last 2 exchanges (4 messages)
                context_lines = []
                for msg in recent_messages:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:100]  # Truncate for brevity
                    context_lines.append(f"{role}: {content}")
                chat_context = "Previous conversation context:\n" + "\n".join(context_lines) + "\n"
                logger.debug("[QUERY CLASSIFIER] Built chat context: %s", chat_context[:200])

            classification_prompt = QUERY_CLASSIFICATION_PROMPT.replace("{question}", question)
            classification_prompt = classification_prompt.replace("{chat_context}", chat_context)

            logger.info("[QUERY CLASSIFIER] ========== Sending prompt to LLM ==========")
            logger.info("[QUERY CLASSIFIER] Full prompt:\n%s", classification_prompt)

            classification = self._call_llm_simple(classification_prompt).strip().lower()

            logger.info("[QUERY CLASSIFIER] ========== LLM Response Received ==========")
            logger.info("[QUERY CLASSIFIER] Raw LLM response: '%s'", classification)

            detected_type = self._parse_classification(classification)

            logger.info("[QUERY CLASSIFIER] ========== Classification Result ==========")
            logger.info("[QUERY CLASSIFIER] Detected type: %s", detected_type)
            return detected_type

        except Exception as e:
            logger.warning("[QUERY CLASSIFIER] ========== LLM Classification Failed ==========")
            logger.warning("[QUERY CLASSIFIER] Error: %s", e)
            logger.warning("[QUERY CLASSIFIER] Falling back to heuristic classification")
            fallback_type = self._fallback_classification(question)
            logger.warning("[QUERY CLASSIFIER] Fallback returned: %s", fallback_type)
            return fallback_type

    def _call_llm_simple(self, prompt: str) -> str:
        """Call the LLM for classification."""
        if self.llm.llm:
            messages = [
                SystemMessage(content="You are a helpful assistant that provides concise answers."),
                HumanMessage(content=prompt)
            ]
            response = self.llm.llm.invoke(messages)
            return response.content.strip()
        elif self.llm.provider == "rules":
            # Rules provider doesn't have real LLM, force fallback classification
            raise RuntimeError("Rules provider - use fallback classification")
        else:
            return self.llm.invoke(prompt)

    def _parse_classification(self, classification: str) -> str:
        """Parse the LLM classification response.

        Args:
            classification: Raw LLM response

        Returns:
            Normalized query type string
        """
        logger.debug("[QUERY CLASSIFIER] Parsing classification: '%s'", classification)

        # Clean up the response - remove common prefixes and suffixes
        cleaned = classification.lower().strip()

        # Remove common LLM preambles
        prefixes_to_remove = [
            'the answer is', 'answer is', 'classification:',
            'type:', 'the type is', 'this is a', 'this is',
            'i would classify this as', 'i classify this as'
        ]
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                logger.debug("[QUERY CLASSIFIER] Removed prefix '%s': '%s'", prefix, cleaned)

        # Get first word/phrase (handle hyphenated types)
        words = cleaned.split()
        first_word = words[0] if words else ''

        logger.debug("[QUERY CLASSIFIER] Extracted first word: '%s'", first_word)

        # Clean up punctuation
        first_word = first_word.strip('.,!?":;()[]{}')
        logger.debug("[QUERY CLASSIFIER] After punctuation cleanup: '%s'", first_word)

        # Normalize underscores to hyphens
        first_word = first_word.replace('_', '-')
        logger.debug("[QUERY CLASSIFIER] After underscore normalization: '%s'", first_word)

        # Check for valid types (exact match)
        if first_word in self.VALID_TYPES:
            logger.debug("[QUERY CLASSIFIER] ✓ Matched valid type: %s", first_word)
            return first_word

        # Try to find valid type anywhere in the response
        logger.debug("[QUERY CLASSIFIER] First word not in valid types, searching response...")
        for valid_type in self.VALID_TYPES:
            if valid_type in cleaned:
                logger.debug("[QUERY CLASSIFIER] ✓ Found valid type in response: %s", valid_type)
                return valid_type

        # Map common response words to actual types
        logger.debug("[QUERY CLASSIFIER] Trying fallback mappings...")
        if first_word in ('recent', 'latest', 'newest', 'oldest'):
            logger.debug("[QUERY CLASSIFIER] Mapped '%s' → filtered-temporal", first_word)
            return 'filtered-temporal'
        elif first_word == 'count':
            logger.debug("[QUERY CLASSIFIER] Mapped 'count' → aggregation")
            return 'aggregation'
        elif 'conversation' in classification or first_word in ('hello', 'hi', 'thanks', 'help'):
            return 'conversation'
        elif 'aggregation' in classification or 'statistic' in classification or 'count' in first_word:
            return 'aggregation'
        elif 'sender' in classification:
            return 'search-by-sender'
        elif 'attachment' in classification:
            return 'search-by-attachment'
        elif 'filtered-temporal' in classification:
            return 'filtered-temporal'
        elif 'temporal' in classification:
            return 'temporal'
        elif 'semantic' in classification:
            return 'semantic'
        elif 'list-previous' in classification or 'previous-results' in classification:
            return 'list-previous-results'
        else:
            logger.debug(
                "[QUERY CLASSIFIER] LLM returned unexpected value: '%s', defaulting to semantic",
                classification,
            )
            return 'semantic'

    def _is_list_previous_request(self, question: str, chat_history: Optional[list]) -> bool:
        """Check if the question is asking to list/show results from a previous query.

        Detects patterns like "list those 78 emails", "show them", "what are they".

        Args:
            question: Current question
            chat_history: Previous conversation messages

        Returns:
            True if this appears to be a follow-up request for listing previous results
        """
        if not chat_history or len(chat_history) < 2:
            # Need at least one exchange (user + assistant) to have previous results
            return False

        question_lower = question.lower()

        # Check for explicit list/show patterns
        for pattern in self.LIST_PREVIOUS_PATTERNS:
            if pattern in question_lower:
                logger.debug(
                    "[QUERY CLASSIFIER] Matched list-previous pattern: '%s'",
                    pattern
                )
                return True

        # Check for numeric reference with list/show verb
        # Examples: "list those 78 emails", "show the 78", "list 78 emails"
        import re
        numeric_list_pattern = r'\b(list|show|display|give me)\b.*\b\d+\b'
        if re.search(numeric_list_pattern, question_lower):
            logger.debug(
                "[QUERY CLASSIFIER] Matched numeric list pattern in: '%s'",
                question_lower
            )
            return True

        # Check for pronouns with list/show verbs
        # Examples: "show them to me", "list all of them"
        pronouns = ['them', 'those', 'these', 'they']
        list_verbs = ['list', 'show', 'display', 'give', 'get', 'retrieve']

        has_pronoun = any(p in question_lower for p in pronouns)
        has_list_verb = any(v in question_lower for v in list_verbs)

        if has_pronoun and has_list_verb:
            logger.debug(
                "[QUERY CLASSIFIER] Matched pronoun + list verb: pronoun=%s, verb=%s",
                has_pronoun, has_list_verb
            )
            return True

        return False

    def _is_contextual_followup(self, question: str, chat_history: list) -> bool:
        """Check if current question is a contextual follow-up that references previous context.

        Args:
            question: Current question
            chat_history: Previous conversation messages

        Returns:
            True if this is a contextual follow-up that should use classification with context
        """
        question_lower = question.lower()

        # Check for contextual reference phrases
        contextual_phrases = [
            'of those', 'from those', 'among them', 'of them', 'out of',
            'from', 'of', 'among', 'from those'
        ]

        has_contextual_reference = any(phrase in question_lower for phrase in contextual_phrases)

        # Check for simple follow-up patterns that don't specify what they're referring to
        # Examples: "who sends most?", "what about senders?", "which ones?"
        is_simple_followup = (
            len(question.split()) <= 6 and  # Short question
            any(phrase in question_lower for phrase in ['who', 'what', 'which', 'how many', 'count']) and
            not any(word in question_lower for word in [
                'all', 'total', 'every', 'overall', 'in general', 'in my'
            ])  # Not asking for everything/general stats
        )

        # Check for numeric references that indicate continuation of previous topic
        has_numeric_reference = any(char.isdigit() for char in question)

        # Look for pronouns that reference previous context
        has_pronouns = any(word in question_lower for word in ['them', 'those', 'they'])

        # Check if we have meaningful chat history to work with
        has_history = bool(chat_history and len(chat_history) >= 2)

        # Enhanced check: Look for very short, ambiguous queries that suggest continuation
        # Examples: "do all 97", "show 97", "list 97"
        is_ambiguous_continuation = (
            len(question.split()) <= 4 and  # Very short
            has_numeric_reference and  # Contains numbers
            not any(word in question_lower for word in ['total', 'overall', 'all', 'every']) and  # Not asking for all emails
            any(phrase in question_lower for phrase in ['do', 'show', 'list', 'get'])  # Action verbs
        )

        # Log for debugging
        logger.debug(
            "[QUERY CLASSIFIER] Contextual analysis - "
            f"has_contextual_reference: {has_contextual_reference}, "
            f"is_simple_followup: {is_simple_followup}, "
            f"has_pronouns: {has_pronouns}, "
            f"has_numeric_reference: {has_numeric_reference}, "
            f"is_ambiguous_continuation: {is_ambiguous_continuation}, "
            f"has_history: {has_history}"
        )

        # This is a contextual follow-up if:
        # 1. It has explicit contextual references, OR
        # 2. It's a simple follow-up with pronouns, OR
        # 3. It's an ambiguous continuation with numbers and we have history
        return (
            has_contextual_reference or
            (is_simple_followup and has_pronouns) or
            (is_ambiguous_continuation and has_history)
        ) and has_history

    def _fallback_classification(self, question: str) -> str:
        """Use heuristics to classify the query when LLM fails.

        Args:
            question: User's question

        Returns:
            Query type string
        """
        question_lower = question.lower()

        # Check for conversational queries
        if any(word in question_lower for word in ['hello', 'hi', 'thanks', 'thank you', 'help', 'what can you']):
            return 'conversation'

        # Check for counting queries
        if 'how many' in question_lower or 'count' in question_lower or 'number of' in question_lower:
            # Check for specific topic
            has_specific_topic = any(word in question_lower for word in [
                'uber', 'amazon', 'linkedin', 'google', 'github', 'facebook',
                'twitter', 'netflix', 'spotify', 'apple', 'microsoft'
            ]) or '@' in question_lower

            if has_specific_topic or 'total' not in question_lower:
                return 'aggregation'

        # Check for temporal patterns
        has_temporal = any(word in question_lower for word in ['recent', 'latest', 'last', 'newest', 'first', 'oldest'])
        has_content_filter = any(word in question_lower for word in ['from', 'about', 'uber', 'amazon', 'linkedin'])

        if has_temporal and has_content_filter:
            return 'filtered-temporal'
        elif has_temporal:
            return 'temporal'
        else:
            return 'semantic'
