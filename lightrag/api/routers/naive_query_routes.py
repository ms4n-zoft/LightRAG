"""
Naive Query Routes - Fast chunk retrieval for chat/AI context
Returns raw text chunks with product metadata
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional
import time
import logging

from lightrag.base import QueryParam

router = APIRouter(tags=["naive-query"])
logger = logging.getLogger(__name__)


class NaiveQueryRequest(BaseModel):
    """Request for naive mode search"""
    query: str = Field(description="User's natural language query")
    chunk_top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of chunks to retrieve (1-50)"
    )


class NaiveQueryResponse(BaseModel):
    """Response with raw text chunks for AI context"""
    chunks_text: str = Field(
        description="Raw text chunks with separators, ready for AI")
    chunk_count: int = Field(description="Number of chunks returned")
    retrieval_time: float = Field(description="Time taken in seconds")


def create_naive_query_routes(rag, api_key: Optional[str] = None):
    """Create naive query routes"""
    from ..utils_api import get_combined_auth_dependency
    combined_auth = get_combined_auth_dependency(api_key)

    @router.post("/query/naive",
                 response_model=NaiveQueryResponse,
                 dependencies=[Depends(combined_auth)])
    async def query_naive(request: NaiveQueryRequest):
        """
        Fast naive mode search - returns raw text chunks with product metadata.

        Perfect for AI chat context:
        - Uses pure vector search (no knowledge graph overhead)
        - Returns product chunks with all metadata (ID, URL, name, pricing, rating, etc.)
        - Fast: ~1-2 seconds typical response time
        - Raw text format ready to feed to LLM

        Example:
        ```json
        {
          "query": "i need crm tools",
          "chunk_top_k": 10
        }
        ```

        Returns raw text with product chunks separated by lines, ready for AI context.
        """
        start_time = time.time()

        try:
            logger.info(
                f"Naive query: {request.query} (k={request.chunk_top_k})")

            # Use naive mode with aquery_data to get chunks
            param = QueryParam(
                mode="naive",
                chunk_top_k=request.chunk_top_k,
                top_k=request.chunk_top_k
            )

            # Get data (entities, relationships, chunks)
            data = await rag.aquery_data(request.query, param=param)

            # Extract chunks
            chunks = data.get("chunks", [])

            # Build raw text response optimized for ai context
            chunks_text_parts = []

            for i, chunk in enumerate(chunks, 1):
                content = chunk.get("content", "")

                # Option 1: Minimal markdown (recommended - ~5 tokens per separator)
                chunks_text_parts.append(f"### Source {i}\n{content}")

                # Option 2: Ultra-minimal (uncomment for max efficiency - ~3 tokens)
                # chunks_text_parts.append(f"[{i}]\n{content}")

                # Option 3: XML-style (good for Claude/structured - ~8 tokens)
                # chunks_text_parts.append(f'<source id="{i}">\n{content}\n</source>')

            # Join with double newline for clear separation
            if chunks_text_parts:
                chunks_text = "\n\n".join(chunks_text_parts)
            else:
                chunks_text = "No relevant products found for your query."

            elapsed = time.time() - start_time

            logger.info(
                f"Naive query completed: {len(chunks)} chunks in {elapsed:.2f}s")

            return NaiveQueryResponse(
                chunks_text=chunks_text,
                chunk_count=len(chunks),
                retrieval_time=elapsed
            )

        except Exception as e:
            logger.error(f"Error in naive query: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=str(e))

    return router
