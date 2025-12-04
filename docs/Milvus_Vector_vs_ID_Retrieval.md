# Understanding Vector vs ID Retrieval in LightRAG

**Date:** December 4, 2025  
**Related:** [Milvus gRPC Message Size Fix](./Milvus_gRPC_Message_Size_Fix.md)

---

## Overview

This document explains the architecture of how LightRAG stores and retrieves data across Milvus (vector database) and Redis (KV storage), and why retrieving **IDs only** from Milvus is both correct and efficient.

---

## Storage Architecture

### Milvus (Vector Database)

Milvus stores **embeddings** (vector representations) of text chunks for similarity search.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MILVUS - chunks collection                          │
├──────────────────┬─────────────────────────────────┬────────────────────────┤
│       ID         │          VECTOR                 │     METADATA           │
│    (string)      │    (1536 floats)                │                        │
├──────────────────┼─────────────────────────────────┼────────────────────────┤
│ "chunk-a1b2c3"   │ [0.012, -0.034, 0.056, ...]     │ full_doc_id, file_path │
│ "chunk-d4e5f6"   │ [0.023, 0.045, -0.067, ...]     │ full_doc_id, file_path │
│ "chunk-g7h8i9"   │ [-0.011, 0.078, 0.021, ...]     │ full_doc_id, file_path │
└──────────────────┴─────────────────────────────────┴────────────────────────┘

Size per row: ~50 bytes (ID) + ~6,144 bytes (vector) + ~100 bytes (metadata)
Vector size: 1536 dimensions × 4 bytes = 6,144 bytes per vector
```

### Redis (KV Storage)

Redis stores the **actual text content** of each chunk.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REDIS - text_chunks namespace                       │
├──────────────────┬──────────────────────────────────────────────────────────┤
│       KEY        │                    VALUE                                 │
│    (chunk ID)    │              (actual text content)                       │
├──────────────────┼──────────────────────────────────────────────────────────┤
│ "chunk-a1b2c3"   │ "Project management software like Asana and Monday..."   │
│ "chunk-d4e5f6"   │ "Slack integrates with Google Workspace to enable..."    │
│ "chunk-g7h8i9"   │ "For teams of 10-50 users, we recommend starting..."     │
└──────────────────┴──────────────────────────────────────────────────────────┘

Size per row: ~50 bytes (key) + ~1,000-2,000 bytes (text content)
```

---

## Why This Separation?

| Storage    | Optimized For                                         | Data Stored                    |
| ---------- | ----------------------------------------------------- | ------------------------------ |
| **Milvus** | Vector similarity search (ANN algorithms, HNSW index) | Embeddings (numerical vectors) |
| **Redis**  | Fast key-value lookups                                | Text content                   |

Milvus excels at answering: _"Which vectors are most similar to this query vector?"_  
Redis excels at answering: _"Give me the text for these chunk IDs."_

---

## The Two Retrieval Approaches

### ❌ OLD: Fetch Vectors, Compute Similarity Client-Side

```python
# Step 1: Fetch ALL vectors from Milvus
result = milvus.query(
    filter='id in ["chunk-a1b2c3", "chunk-d4e5f6", ...]',  # 9,759 IDs
    output_fields=["vector"]  # ← REQUESTING ACTUAL VECTORS
)

# Milvus returns ~60MB of data:
# {
#     "chunk-a1b2c3": [0.012, -0.034, 0.056, ... 1536 floats],
#     "chunk-d4e5f6": [0.023, 0.045, -0.067, ... 1536 floats],
#     ... 9,759 entries
# }

# Step 2: Compute similarity in Python (slow, CPU-bound)
for chunk_id, chunk_vector in result.items():
    similarity = cosine_similarity(query_vector, chunk_vector)

# Step 3: Sort and take top 120
top_chunks = sorted(similarities, reverse=True)[:120]
```

**Problems:**

- Transfers **~60MB** over gRPC (exceeds 4MB limit)
- Wastes network bandwidth
- CPU-intensive similarity computation in Python
- Defeats the purpose of having a vector database with optimized indexes

---

### ✅ NEW: Let Milvus Compute Similarity Server-Side

```python
# Step 1: Ask Milvus to search within candidate IDs
result = milvus.search(
    data=[query_vector],                                    # Send query vector (~6KB)
    filter='id in ["chunk-a1b2c3", "chunk-d4e5f6", ...]',  # Filter to candidates
    limit=120,                                              # Only return top 120
    output_fields=["id"]                                    # ← ONLY RETURN IDs
)

# Milvus returns ~6KB of data:
# [
#     {"id": "chunk-x1y2z3", "distance": 0.92},
#     {"id": "chunk-a1b2c3", "distance": 0.89},
#     ... 120 entries
# ]

# Step 2: Fetch text content from Redis
texts = redis.get_by_ids(["chunk-x1y2z3", "chunk-a1b2c3", ...])
```

**Benefits:**

- Transfers only **~12KB** total (query + response)
- Milvus uses optimized HNSW index for fast similarity search
- No Python CPU work for similarity computation
- Works within gRPC message limits

---

## Data Flow Comparison

### Old Flow (Broken at Scale)

```
                    60MB (FAILS gRPC limit!)
                    ┌──────────────┐
User Query ──► Milvus ──► [ALL VECTORS] ──► Python computes ──► [120 IDs] ──► Redis ──► [Text]
                    └──────────────┘        similarity
```

### New Flow (Efficient)

```
                    ~6KB              ~6KB                         ~150KB
                    ┌────┐            ┌────┐                       ┌─────┐
User Query ──► Milvus ──► [Query Vec] ──► [120 IDs + Scores] ──► Redis ──► [Text]
                    └────┘            └────┘                       └─────┘
                    (server-side similarity computation)
```

---

## Frequently Asked Questions

### Q: Do we lose information by only getting IDs?

**No.** The ID is the **key** to look up everything else:

- Text content → Redis (text_chunks)
- Metadata → Already retrieved during KG expansion
- Similarity score → Returned by Milvus search

### Q: Is the similarity score the same?

**Yes.** Milvus computes cosine similarity using the same formula:

```
cosine_similarity = dot(A, B) / (norm(A) * norm(B))
```

The only difference is float32 (Milvus) vs float64 (Python), which causes negligible precision differences (~0.0001).

### Q: Why not store text in Milvus?

Milvus is optimized for **vector operations**, not text storage:

- Vector indexes (HNSW, IVF) don't help with text retrieval
- Text in Milvus would bloat memory usage
- Redis is purpose-built for fast key-value lookups

### Q: What if we need vectors for something else later?

The `get_vectors_by_ids()` method still exists (now batched for safety). Use it when you genuinely need the vector data, such as:

- Debugging embedding quality
- Re-indexing operations
- Vector arithmetic (averaging, clustering)

For normal query operations, you should **never** need the vectors after similarity search.

---

## Size Calculations

### Vector Size

```
1 vector = 1536 dimensions × 4 bytes (float32) = 6,144 bytes ≈ 6KB
```

### Old Approach (9,759 candidates)

```
Data transferred = 9,759 vectors × 6KB = ~60MB ❌ (exceeds 4MB gRPC limit)
```

### New Approach (120 results)

```
Request:  1 query vector × 6KB                    = ~6KB
Response: 120 results × ~50 bytes (ID + score)    = ~6KB
Total:                                              ~12KB ✅
```

### Text Retrieval (Redis)

```
120 chunks × ~1.2KB average text = ~150KB ✅ (fast KV lookup)
```

---

## Code Reference

### Optimized Search (`search_by_ids`)

**File:** `lightrag/kg/milvus_impl.py`

```python
async def search_by_ids(
    self,
    query_embedding: list[float],
    candidate_ids: list[str],
    top_k: int,
    min_similarity: float | None = None,
) -> list[str]:
    """Server-side filtered similarity search - returns only IDs"""

    results = self._client.search(
        collection_name=self.final_namespace,
        data=[query_embedding],
        filter=f'id in ["{id_list}"]',
        limit=top_k,
        output_fields=["id"],  # Only IDs, not vectors!
        search_params={"metric_type": "COSINE"},
    )
    return [dp["id"] for dp in results[0]]
```

### Text Retrieval (Redis)

**File:** `lightrag/kg/redis_impl.py`

```python
async def get_by_ids(self, ids: list[str]) -> list[dict]:
    """Fast key-value lookup for text content"""
    return [await self._redis.get(id) for id in ids]
```

---

## Summary

| Aspect                     | Old Approach         | New Approach           |
| -------------------------- | -------------------- | ---------------------- |
| **What's transferred**     | All vectors (~60MB)  | Only IDs (~6KB)        |
| **Similarity computation** | Client-side (Python) | Server-side (Milvus)   |
| **gRPC compliance**        | ❌ Exceeds 4MB limit | ✅ Well under limit    |
| **Performance**            | Slow (network + CPU) | Fast (optimized index) |
| **Text retrieval**         | Same (Redis)         | Same (Redis)           |

**Key insight:** Vectors are only needed for similarity computation. Once Milvus tells us which chunks are most similar (via IDs), we fetch the actual text from Redis. We never need to transfer the vectors themselves.
