# Incident Report: Milvus gRPC Message Size Exceeded Error

**Date:** December 4, 2025  
**Severity:** High  
**Status:** Resolved  
**Affected Component:** Milvus Vector Database Integration

---

## Summary

Queries that matched a large number of entities/relations (9,000+) were failing with a gRPC message size exceeded error when the system attempted to retrieve chunk vectors for similarity ranking.

## Error Message

```
grpc: received message larger than max (60349766 vs. 4194304)
ERROR: [] Error retrieving vectors by IDs from chunks: <_MultiThreadedRendezvous of RPC that terminated with:
    status = StatusCode.RESOURCE_EXHAUSTED
    details = "grpc: received message larger than max (60349766 vs. 4194304)"
```

## Root Cause Analysis

### The Problem

1. A user query matched **40 entities with 9,388 relations** in the knowledge graph
2. These entities/relations were associated with **9,759 unique text chunks**
3. The `pick_by_vector_similarity()` function attempted to retrieve ALL chunk vectors to compute similarity scores client-side
4. Each vector has **1,536 dimensions** (float32), resulting in:
   - `9,759 chunks × 1,536 dims × 4 bytes ≈ 60MB` of data
5. Milvus gRPC has a default **4MB message size limit**, causing the query to fail

### Why This Design Was Inefficient

The original implementation:

```python
# OLD: Fetch ALL vectors, then compute similarity in Python
chunk_vectors = await chunks_vdb.get_vectors_by_ids(all_chunk_ids)  # 60MB transfer!
for chunk_id in all_chunk_ids:
    similarity = cosine_similarity(query_embedding, chunk_vectors[chunk_id])
```

This approach:

- Transfers massive amounts of data over the network
- Defeats the purpose of having an indexed vector database
- Performs brute-force similarity computation on the client

---

## Solution

### Two-Layer Fix Applied

#### 1. Primary Fix: Native Filtered Vector Search (`search_by_ids`)

Added a new optimized method that uses Milvus's native filtered search capabilities:

**File:** `lightrag/kg/milvus_impl.py`

```python
async def search_by_ids(
    self,
    query_embedding: list[float],
    candidate_ids: list[str],
    top_k: int,
) -> list[str]:
    """Search for top_k most similar vectors from a filtered set of candidate IDs.

    Uses Milvus native filtered search - much more efficient than fetching all vectors.
    """
    # Batch candidate IDs to avoid filter expression length limits
    for i in range(0, len(candidate_ids), 1000):
        batch_ids = candidate_ids[i : i + 1000]
        filter_expr = f'id in ["{id_list}"]'

        # Let Milvus do the similarity search with its HNSW index
        results = self._client.search(
            collection_name=self.final_namespace,
            data=[query_embedding],
            filter=filter_expr,
            limit=top_k,
            search_params={"metric_type": "COSINE"},
        )
```

**Benefits:**

- Milvus uses its **HNSW index** for efficient similarity search
- Only **IDs are returned** (not full vectors) - minimal data transfer
- Server-side filtering and ranking

#### 2. Safety Net: Batched Vector Retrieval (`get_vectors_by_ids`)

For fallback scenarios, the legacy method now batches requests:

```python
async def get_vectors_by_ids(self, ids: list[str]) -> dict[str, list[float]]:
    # Batch size: 500 vectors * 1536 dims * 4 bytes ≈ 3MB (under 4MB limit)
    batch_size = 500

    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        result = self._client.query(
            collection_name=self.final_namespace,
            filter=filter_expr,
            output_fields=["vector"],
        )
```

#### 3. Updated Query Flow (`pick_by_vector_similarity`)

**File:** `lightrag/utils.py`

```python
# NEW: Try optimized method first
if hasattr(chunks_vdb, "search_by_ids"):
    selected_chunks = await chunks_vdb.search_by_ids(
        query_embedding=query_embedding,
        candidate_ids=all_chunk_ids,
        top_k=num_of_chunks,
    )
    if selected_chunks:
        return selected_chunks

# Fallback to legacy method (now with batching)
chunk_vectors = await chunks_vdb.get_vectors_by_ids(all_chunk_ids)
```

---

## Performance Comparison

| Metric                   | Before (Broken) | After (Fixed)                |
| ------------------------ | --------------- | ---------------------------- |
| **Data transferred**     | ~60MB (fails)   | ~0.1MB                       |
| **Computation location** | Client-side     | Server-side (indexed)        |
| **Network round trips**  | 1 (fails)       | 10 (batched filter searches) |
| **Expected latency**     | N/A (error)     | ~1-2 seconds                 |

---

## Files Changed

| File                         | Changes                                                                                                    |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `lightrag/base.py`           | Added `search_by_ids()` abstract method to `BaseVectorStorage`                                             |
| `lightrag/kg/milvus_impl.py` | Implemented `search_by_ids()` with native Milvus filtered search; Added batching to `get_vectors_by_ids()` |
| `lightrag/utils.py`          | Updated `pick_by_vector_similarity()` to use optimized method first                                        |

---

## Testing Recommendations

1. **Large Query Test:** Execute a query that matches many entities (1000+) and verify no gRPC errors
2. **Result Consistency:** Compare chunk selection results between old and new methods on smaller datasets
3. **Performance Benchmark:** Measure query latency improvement for broad queries

---

## Rollback Plan

If issues arise, revert to the legacy method by:

1. Removing the `search_by_ids` call in `lightrag/utils.py`
2. The batched `get_vectors_by_ids` will still work as a safer fallback

---

## Lessons Learned

1. **Use vector database features:** Always prefer native DB operations over client-side computation
2. **Consider scale:** Design for worst-case scenarios with large result sets
3. **Batch operations:** When transferring data, respect protocol limits (gRPC 4MB default)
4. **Layered fixes:** Implement both optimized path and safe fallback

---

## Related Issues

- Milvus gRPC configuration: Can also increase `proxy.grpc.serverMaxRecvSize` server-side, but application-level fix is more robust
