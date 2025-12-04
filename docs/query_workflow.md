┌─────────────────────────────────────────────────────────────────────────────────┐
│                           USER QUERY: /query                                    │
│  "What project management tools integrate with Slack and Google Workspace?"     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  1. API LAYER (query_routes.py)                                                 │
│     - Receives QueryRequest with mode="hybrid" (or mix/local/global/naive)      │
│     - Converts to QueryParam                                                    │
│     - Calls rag.aquery(query, param)                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  2. LIGHTRAG CORE (lightrag.py → operate.py)                                    │
│     - Computes query embedding ONCE (reused everywhere)                         │
│     - Extracts keywords from query using LLM                                    │
│       → high_level_keywords: ["Project Management", "Integration"]              │
│       → low_level_keywords: ["Slack", "Google Workspace", "tools"]              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
┌──────────────────────────────────┐  ┌──────────────────────────────────┐
│  3A. LOCAL SEARCH (Entities)     │  │  3B. GLOBAL SEARCH (Relations)   │
│  ────────────────────────────────│  │  ────────────────────────────────│
│  Query Milvus entities_vdb       │  │  Query Milvus relationships_vdb  │
│  with low_level_keywords         │  │  with high_level_keywords        │
│                                  │  │                                  │
│  Returns: 40 entities            │  │  Returns: 40 relations           │
│  (with source_id → chunk refs)   │  │  (with source_id → chunk refs)   │
└──────────────────────────────────┘  └──────────────────────────────────┘
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  4. KNOWLEDGE GRAPH EXPANSION (Neo4j)                                           │
│     - For each entity found, query Neo4j for connected nodes/edges              │
│     - Expands: 40 entities → 91 entities, 9,427 relations                       │
│     - Each entity/relation has source_id field pointing to text chunks          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  5. COLLECT CANDIDATE CHUNK IDs                                                 │
│     - Extract all chunk IDs from entity.source_id and relation.source_id        │
│     - Result: 9,759 unique chunk IDs (this is where the 60MB problem was!)      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  6. CHUNK SELECTION (pick_by_vector_similarity) ← THE FIX IS HERE               │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  OLD FLOW (BROKEN):                                                      │   │
│  │  1. get_vectors_by_ids(9759 chunk IDs) → Fetch 60MB of vectors          │   │
│  │  2. For each vector, compute cosine_similarity(query_emb, chunk_emb)    │   │
│  │  3. Sort by similarity, take top 120                                    │   │
│  │  ❌ FAILS: gRPC message size exceeded (60MB > 4MB limit)                │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  NEW FLOW (FIXED):                                                       │   │
│  │  1. search_by_ids(query_emb, 9759 chunk IDs, top_k=120, threshold=0.2)  │   │
│  │     → Milvus does filtered vector search SERVER-SIDE                    │   │
│  │     → Only returns 120 IDs (not vectors!) sorted by similarity          │   │
│  │  2. Data transferred: ~10KB (just IDs) vs 60MB                          │   │
│  │  ✅ WORKS: Fast, efficient, no gRPC limit issues                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  Output: 120 selected chunk IDs                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  7. FETCH CHUNK CONTENT (Redis KV Storage)  ← YES, we fetch chunks here!        │
│     - text_chunks_db.get_by_ids(120 chunk IDs)                                  │
│     - Returns actual text content for each chunk                                │
│     - This is from Redis (KV store), NOT Milvus (vector store)                  │
│     - Each chunk is ~1-2KB of text, so 120 chunks ≈ 150KB (very manageable)     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  8. BUILD CONTEXT                                                               │
│     - Combine: entity descriptions + relation descriptions + chunk texts        │
│     - Apply token limits (max_total_tokens, max_entity_tokens, etc.)            │
│     - Format into structured context for LLM                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  9. LLM GENERATION (Azure OpenAI)                                               │
│     - System prompt + context + user query                                      │
│     - Generate final response                                                   │
│     - ~26,637 tokens input → ~5,862 chars output                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  10. RETURN RESPONSE                                                            │
│      QueryResponse(response="Based on your requirements...")                    │
└─────────────────────────────────────────────────────────────────────────────────┘