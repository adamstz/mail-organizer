#!/usr/bin/env python3
"""Simple integration test for chat history functionality."""

import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from src.services.rag_engine import RAGQueryEngine
from src.services.llm_processor import LLMProcessor
from src.storage.memory_storage import InMemoryStorage
from src.services.embedding_service import EmbeddingService
from src.models.message import MailMessage
from unittest.mock import Mock, MagicMock


@pytest.mark.skip(reason="Requires real LLM provider, not rules provider")
def test_basic_functionality():
    """Test basic chat history functionality."""
    print("🧪 Testing Chat History Functionality")
    print("=" * 50)
    
    # Set up environment for testing
    os.environ['LLM_PROVIDER'] = 'rules'
    
    try:
        # Create components
        storage = InMemoryStorage()
        llm = LLMProcessor()
        # Mock embedding service to avoid downloading models
        embedder = MagicMock(spec=EmbeddingService)
        embedder.embedding_dim = 384
        embedder.embed_text.return_value = [0.1] * 384
        embedder.embed_batch.return_value = [[0.1] * 384]
        rag_engine = RAGQueryEngine(storage, embedder, llm, top_k=5)
        
        print(f"✅ Components initialized with {llm.provider}/{llm.model}")
        
        # Add test data
        test_email = MailMessage(
            id="test1",
            subject="Special Offer - 50% Off",
            snippet="Limited time offer on all items",
            from_="marketing@shop.com",
            internal_date=1704096000000,
            labels=["promotions"]
        )
        storage.save_message(test_email)
        print("✅ Test email added to storage")
        
        # Test 1: Direct query (baseline)
        print("\n📋 Test 1: Direct Classification Query")
        result1 = rag_engine.query("how many promotional emails do I have?")
        print(f"Query Type: {result1.get('query_type')}")
        print(f"Answer: {result1.get('answer', 'No answer')[:100]}...")
        print(f"Confidence: {result1.get('confidence')}")
        
        # Test 2: Follow-up query with context
        print("\n📋 Test 2: Follow-up Query with Context")
        chat_history = [
            {"role": "user", "content": "how many promotional emails do I have"},
            {"role": "assistant", "content": "You have promotional emails."},
        ]
        
        result2 = rag_engine.query(
            question="of those, who sends the most?",
            chat_history=chat_history
        )
        print(f"Query Type: {result2.get('query_type')}")
        print(f"Answer: {result2.get('answer', 'No answer')[:100]}...")
        print(f"Confidence: {result2.get('confidence')}")
        
        # Test 3: Multiple topic changes
        print("\n📋 Test 3: Multiple Topic Changes")
        complex_history = [
            {"role": "user", "content": "how many promotional emails?"},
            {"role": "assistant", "content": "promotional emails"},
            {"role": "user", "content": "show me job applications"},
            {"role": "assistant", "content": "job-related emails"},
        ]
        
        result3 = rag_engine.query(
            question="from the job ones, any interviews?",
            chat_history=complex_history
        )
        print(f"Query Type: {result3.get('query_type')}")
        print(f"Answer: {result3.get('answer', 'No answer')[:100]}...")
        print(f"Confidence: {result3.get('confidence')}")
        
        # Test 4: No context fallback
        print("\n📋 Test 4: No Context Fallback")
        result4 = rag_engine.query("who sends most?")
        print(f"Query Type: {result4.get('query_type')}")
        print(f"Answer: {result4.get('answer', 'No answer')[:100]}...")
        print(f"Confidence: {result4.get('confidence')}")
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        
        tests = [
            ("Direct Classification", result1.get('query_type') == 'classification'),
            ("Follow-up with Context", result2.get('query_type') == 'classification'),
            ("Multiple Topics", result3.get('query_type') == 'classification'),
            ("No Context Fallback", result4.get('query_type') == 'classification')
        ]
        
        passed = 0
        for name, success in tests:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status}: {name}")
            if success:
                passed += 1
        
        print(f"\nOverall: {passed}/{len(tests)} tests passed ({passed/len(tests)*100:.1f}%)")
        
        if passed == len(tests):
            print("🎉 ALL TESTS PASSED!")
        else:
            print("⚠️  Some tests failed.")
        assert passed == len(tests), f"Only {passed}/{len(tests)} tests passed"

    except Exception as e:
        print(f"❌ SETUP FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    test_basic_functionality()
