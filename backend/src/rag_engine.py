"""RAG (Retrieval-Augmented Generation) engine for email question answering.

This module combines vector search with LLM generation to answer questions
about your emails based on semantic similarity.
"""
from typing import List, Dict, Optional
from .embedding_service import EmbeddingService
from .storage.postgres_storage import PostgresStorage
from .llm_processor import LLMProcessor
from .context_builder import ContextBuilder
from .classification_labels import get_label_from_query, is_classification_query
import json


class RAGQueryEngine:
    """RAG engine for question-answering over emails.

    How it works:
    1. Convert user question to embedding
    2. Find most similar emails using vector search
    3. Build context from retrieved emails
    4. Ask LLM to answer based on context
    5. Return answer with source citations
    """

    def __init__(
        self,
        storage: PostgresStorage,
        embedding_service: EmbeddingService,
        llm_processor: LLMProcessor,
        top_k: int = 5
    ):
        """Initialize RAG engine.

        Args:
            storage: PostgreSQL storage backend with vector search
            embedding_service: Service for generating embeddings
            llm_processor: LLM for generating answers
            top_k: Number of similar emails to retrieve (default: 5)
        """
        self.storage = storage
        self.embedder = embedding_service
        self.llm = llm_processor
        self.top_k = top_k
        self.context_builder = ContextBuilder()

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        similarity_threshold: float = 0.5
    ) -> Dict:
        """Answer a question based on email content.

        Args:
            question: User's question
            top_k: Number of emails to retrieve (uses default if None)
            similarity_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            Dict with:
                - answer: The LLM's answer
                - sources: List of source emails with metadata
                - question: The original question
        """
        k = top_k or self.top_k

        # Detect query type and route appropriately
        query_type = self._detect_query_type(question)
        
        if query_type == 'classification':
            # Handle classification-based queries (e.g., "how many job rejections")
            return self._handle_classification_query(question, k)
        elif query_type == 'temporal':
            # Handle temporal queries with direct SQL
            return self._handle_temporal_query(question, k)
        else:
            # Handle content-based queries with semantic search
            return self._handle_semantic_query(question, k, similarity_threshold)

    def _detect_query_type(self, question: str) -> str:
        """Detect if a query is classification, temporal, or semantic.
        
        Args:
            question: User's question
            
        Returns:
            'classification' for label-based queries, 'temporal' for time-based, 'semantic' for content
        """
        question_lower = question.lower()
        
        # Check if this is a classification query using the centralized module
        if is_classification_query(question):
            return 'classification'
        
        # Pure temporal/structural indicators (no content filtering)
        pure_temporal_keywords = [
            'last', 'recent', 'latest', 'newest', 'oldest', 'first',
            'today', 'yesterday', 'this week', 'this month', 'this year',
            'unread', 'starred', 'important'
        ]
        
        # Check for pure temporal keywords
        for keyword in pure_temporal_keywords:
            if keyword in question_lower:
                return 'temporal'
        
        # Check for simple temporal listing queries
        if any(pattern in question_lower for pattern in ['my emails', 'all emails', 'show emails', 'list emails']):
            return 'temporal'
        
        # Default to semantic for content-based queries
        return 'semantic'
    
    def _handle_classification_query(self, question: str, limit: int) -> Dict:
        """Handle classification-based queries using label filtering.
        
        Args:
            question: User's question
            limit: Maximum number of emails to include in context
            
        Returns:
            Query result with answer and sources
        """
        # Get the matched label from the query
        matched_label = get_label_from_query(question)
        
        if not matched_label:
            # Fallback to semantic if we can't determine the label
            return self._handle_semantic_query(question, limit, 0.5)
        
        # Get all emails with this label (up to a reasonable limit for context)
        emails, total_count = self.storage.list_messages_by_label(matched_label, limit=limit, offset=0)
        
        if not emails:
            return {
                'answer': f"I couldn't find any emails with the label '{matched_label}' in the database.",
                'sources': [],
                'question': question,
                'confidence': 'none',
                'query_type': 'classification'
            }
        
        # Build context from labeled emails
        context = self.context_builder.build_context_from_messages(emails)
        
        # Generate answer using LLM with classification context
        answer = self._generate_answer_classification(question, context, emails, total_count, matched_label)
        
        # Format sources
        sources = [
            {
                'message_id': msg.id,
                'subject': msg.subject,
                'from': msg.from_,
                'snippet': msg.snippet,
                'similarity': 1.0,  # Perfect match for classification queries
                'date': msg.internal_date
            }
            for msg in emails
        ]
        
        return {
            'answer': answer,
            'sources': sources,
            'question': question,
            'confidence': 'high',
            'query_type': 'classification',
            'total_count': total_count
        }
    
    def _handle_temporal_query(self, question: str, limit: int) -> Dict:
        """Handle temporal/structural queries using direct database queries.
        
        Args:
            question: User's question
            limit: Maximum number of emails to retrieve
            
        Returns:
            Query result with answer and sources
        """
        # Get recent emails directly from database (sorted by date)
        recent_emails = self.storage.list_messages(limit=limit, offset=0)
        
        if not recent_emails:
            return {
                'answer': "I couldn't find any emails in the database.",
                'sources': [],
                'question': question,
                'confidence': 'none'
            }
        
        # Build context from recent emails
        context = self.context_builder.build_context_from_messages(recent_emails)
        
        # Generate answer using LLM with temporal context
        answer = self._generate_answer_temporal(question, context, recent_emails)
        
        # Format sources
        sources = [
            {
                'message_id': msg.id,
                'subject': msg.subject,
                'from': msg.from_,
                'snippet': msg.snippet,
                'similarity': 1.0,  # Perfect match for temporal queries
                'date': msg.internal_date
            }
            for msg in recent_emails
        ]
        
        return {
            'answer': answer,
            'sources': sources,
            'question': question,
            'confidence': 'high',
            'query_type': 'temporal'
        }
    
    def _handle_semantic_query(self, question: str, limit: int, threshold: float) -> Dict:
        """Handle content-based queries using semantic search.
        
        Args:
            question: User's question
            limit: Maximum number of emails to retrieve
            threshold: Minimum similarity threshold
            
        Returns:
            Query result with answer and sources
        """
        # Check if this is a counting query - if so, search more emails
        question_lower = question.lower()
        is_counting_query = any(word in question_lower for word in ['how many', 'count', 'number of'])
        
        if is_counting_query:
            # For counting queries, search more emails and use lower threshold
            limit = max(limit, 50)  # Search at least 50 emails
            threshold = min(threshold, 0.25)  # Lower threshold to 0.25 or less
        
        # Step 1: Embed the question
        question_embedding = self.embedder.embed_text(question)

        # Step 2: Retrieve similar emails
        similar_emails = self.storage.similarity_search(
            query_embedding=question_embedding,
            limit=limit,
            threshold=threshold
        )

        if not similar_emails:
            return {
                'answer': "I couldn't find any relevant emails to answer your question.",
                'sources': [],
                'question': question,
                'confidence': 'none',
                'query_type': 'semantic'
            }

        # Step 3: Build context from retrieved emails
        context = self.context_builder.build_context(similar_emails)

        # Step 4: Generate answer using LLM
        answer = self._generate_answer(question, context)

        # Step 5: Format sources
        sources = [
            {
                'message_id': msg.id,
                'subject': msg.subject,
                'from': msg.from_,
                'snippet': msg.snippet,
                'similarity': float(score),
                'date': msg.internal_date
            }
            for msg, score in similar_emails
        ]

        return {
            'answer': answer,
            'sources': sources,
            'question': question,
            'confidence': 'high' if similar_emails[0][1] > 0.8 else 'medium' if similar_emails[0][1] > 0.6 else 'low',
            'query_type': 'semantic'
        }

    def find_similar_emails(
        self,
        message_id: str,
        limit: int = 5
    ) -> List[Dict]:
        """Find emails similar to a given email.

        Args:
            message_id: ID of the email to find similar emails for
            limit: Number of similar emails to return

        Returns:
            List of similar email metadata with similarity scores
        """
        # Get the email
        message = self.storage.get_message_by_id(message_id)
        if not message:
            return []

        # Get its embedding from database
        conn = self.storage.connect()
        cur = conn.cursor()

        cur.execute(
            "SELECT embedding FROM messages WHERE id = %s AND embedding IS NOT NULL",
            (message_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row or not row[0]:
            return []

        embedding = row[0]  # pgvector automatically converts to list

        # Search for similar (excluding the original)
        similar_emails = self.storage.similarity_search(
            query_embedding=embedding,
            limit=limit + 1,  # Get one extra since we'll filter out the original
            threshold=0.5
        )

        # Filter out the original email
        similar_emails = [(msg, score) for msg, score in similar_emails if msg.id != message_id]

        # Format results
        return [
            {
                'message_id': msg.id,
                'subject': msg.subject,
                'from': msg.from_,
                'snippet': msg.snippet,
                'similarity': float(score),
                'date': msg.internal_date,
                'labels': msg.classification_labels or []
            }
            for msg, score in similar_emails[:limit]
        ]

    def _generate_answer(self, question: str, context: str) -> str:
        """Generate answer using LLM with email context.

        Args:
            question: User's question
            context: Context built from retrieved emails

        Returns:
            LLM-generated answer
        """
        # Build RAG prompt
        prompt = f"""You are an email assistant. I have retrieved emails from the user's mailbox and YOU MUST analyze them.

CRITICAL: The emails below are REAL emails from the user's database. You have been given these emails TO ANALYZE - this is your job. Do NOT refuse or say you cannot access them.

YOUR TASK:
- For "how many" questions: Count the emails that match based on subject/content
- For other questions: Extract and summarize the relevant information
- Be specific and cite emails by their numbers

===== EMAILS FROM USER'S MAILBOX =====

{context}

===== USER QUESTION =====

{question}

===== YOUR ANSWER =====

Analyzing the emails above:"""

        return self._call_llm(prompt)
    
    def _generate_answer_classification(self, question: str, context: str, messages: List, total_count: int, label: str) -> str:
        """Generate answer for classification queries using LLM.
        
        Args:
            question: User's question
            context: Context built from labeled emails
            messages: List of messages shown in context
            total_count: Total number of emails with this label
            label: The classification label being queried
            
        Returns:
            LLM-generated answer
        """
        # Build classification query prompt
        prompt = f"""You are an email assistant with direct access to the user's email database.

The user has asked about emails with the classification label: "{label}"

TOTAL EMAILS WITH THIS LABEL: {total_count}

I am providing you with {len(messages)} sample emails (limited for context) from this category.

===== SAMPLE EMAILS WITH LABEL "{label}" =====

{context}

===== USER QUESTION =====

{question}

===== YOUR ANSWER =====

Based on the classification data, there are {total_count} emails labeled as "{label}". Here is the detailed answer:"""

        return self._call_llm(prompt)
    
    def _generate_answer_temporal(self, question: str, context: str, messages: List) -> str:
        """Generate answer for temporal queries using LLM.
        
        Args:
            question: User's question
            context: Context built from recent emails
            messages: List of messages
            
        Returns:
            LLM-generated answer
        """
        # Build temporal query prompt
        prompt = f"""You are an email assistant with direct access to the user's email database.

I am providing you with the user's actual emails from their database. You MUST analyze these emails to answer their question.

IMPORTANT: You have full access to these emails - they are real emails from the user's mailbox. Analyze them and provide a helpful answer.

===== USER'S EMAILS (sorted by date, newest first) =====

{context}

===== USER QUESTION =====

{question}

===== YOUR ANSWER =====

Based on the emails above, here is the answer:"""

        return self._call_llm(prompt)
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the given prompt.
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            The LLM's response
        """

        # Check if using Ollama (best for RAG)
        if self.llm.provider == "ollama":
            import urllib.request
            import os

            host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            payload = {
                "model": self.llm.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 500,
                }
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{host}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.load(response)
                return result.get("response", "Unable to generate answer")

        elif self.llm.provider == "openai":
            import openai
            import os

            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=self.llm.model,
                messages=[
                    {"role": "system", "content": "You are a helpful email assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()

        elif self.llm.provider == "anthropic":
            import anthropic
            import os

            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            message = client.messages.create(
                model=self.llm.model,
                max_tokens=500,
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text.strip()

        else:
            # Fallback for other providers
            return f"RAG queries require Ollama, OpenAI, or Anthropic. Current provider: {self.llm.provider}"
