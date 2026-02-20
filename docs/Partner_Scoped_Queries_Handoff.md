# Partner-Scoped Queries — Handoff Guide

## What it does

When a query includes `partner_id`, the system restricts the RAG context to only products belonging to that partner. The LLM only sees (and can only recommend) in-scope products.

**Flow**: API request with `partner_id` → load partner's product IDs from MongoDB → over-fetch from vector DB → post-filter entities, relations, and chunks to only those matching the partner's products → send filtered context to LLM.

## How to use it

### 1. Send a scoped query

Add `partner_id` to your `/query` request:

```json
{
  "query": "Best CRM tools for a sales team of 20",
  "mode": "hybrid",
  "partner_id": "peko",
  "top_k": 60,
  "chunk_top_k": 30,
  "max_total_tokens": 64000,
  "user_prompt": "Return a JSON array of product recommendations with product_id and reasoning."
}
```

Key fields:
- **`query`** — the business question (keep it clean, no formatting instructions here — this text goes through keyword extraction)
- **`partner_id`** — partner identifier (currently only `"peko"` is configured)
- **`mode`** — use `"hybrid"` for best results (combines local graph + global + vector search)
- **`user_prompt`** — formatting/output instructions for the LLM (injected after context retrieval, does not affect search)
- **`max_total_tokens`** — set generously (e.g. `64000`) to ensure chunks make it into the context alongside entities and relations

### 2. Without partner_id

Omit the field or set it to `null` — the query runs unscoped against the full knowledge graph as usual.

### 3. Authentication

All requests require the `X-API-Key` header:
```
X-API-Key: <your-api-key>
```

## Architecture at a glance

```
lightrag/services/partner_scope_service.py   ← partner config + MongoDB loader + cache
lightrag/base.py                             ← QueryParam.scope_product_ids field
lightrag/operate.py                          ← _apply_scope_filter(), _is_in_scope()
lightrag/api/routers/query_routes.py         ← resolves partner_id → scope in endpoints
```

### Scope filter details

1. **Over-fetch**: When scope is active, the system fetches `3×` the requested `top_k` / `chunk_top_k` from vector DB to compensate for items that will be filtered out.
2. **Post-filter**: Entities, relations, and chunks are filtered by checking if their `file_path` contains a `product_id:<hex>` that belongs to the partner's product set.
3. **Merged-chunk filter**: A final pass removes any chunks that slipped through merging from out-of-scope products.

### Caching

Product IDs are cached in memory for 1 hour (configurable via `PARTNER_SCOPE_CACHE_TTL`). The cache is per-partner and uses an async lock to prevent thundering herd on expiry.

## Adding a new partner

1. **Create the partner's MongoDB database** with a `products` collection. Each document needs an `_id` matching the product IDs in the RAG store.

2. **Add env vars** for the new partner's MongoDB connection:
   ```
   NEWPARTNER_MONGO_URI=mongodb://...
   NEWPARTNER_DB_NAME=NewPartnerDB
   ```

3. **Add a `PartnerConfig`** in `lightrag/services/partner_scope_service.py`:
   ```python
   PARTNER_CONFIGS: dict[str, PartnerConfig] = {
       "peko": PartnerConfig(...),
       "newpartner": PartnerConfig(
           partner_id="newpartner",
           mongo_uri=os.getenv("NEWPARTNER_MONGO_URI", "mongodb://localhost:27017/"),
           db_name=os.getenv("NEWPARTNER_DB_NAME", "NewPartnerDB"),
           product_collection="products",
       ),
   }
   ```

4. **Rebuild and deploy** the Docker container.

5. **Test** with:
   ```bash
   curl -X POST http://localhost:9621/query \
     -H "Content-Type: application/json" \
     -H "X-API-Key: <key>" \
     -d '{"query": "test query", "mode": "hybrid", "partner_id": "newpartner"}'
   ```

## Logging

All scope operations are logged with `[partner-scope]` prefix:
```
[partner-request:peko] /query received with partner scope
[partner-request:peko] scope resolved → 4741 product IDs loaded into QueryParam
[partner-scope] scope filter ACTIVE with 4741 product IDs, over-fetching 3x
[partner-scope] context filter applied — entities: 314→232, relations: 4802→3551, chunks: 0→0
[partner-scope] merged-chunk filter: 354→319 (dropped 35 out-of-scope chunks)
```

## Testing

Run the E2E test suite:
```bash
python tests/test_scoped_query_e2e.py --max-cases 24 --max-recos 8 --timeout 300
```

This sends 24 diverse queries with `partner_id=peko`, parses the LLM's JSON response, and validates every returned `product_id` exists in the partner's MongoDB. Results are written to `tests/scope/` (JSON) and `docs/Partner_Scoping_Test_Report.md` (markdown).

## Environment setup

See [Partner_Scope_Environment_Variables.md](Partner_Scope_Environment_Variables.md) for all required and optional env vars.
