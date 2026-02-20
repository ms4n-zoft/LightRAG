"""
Test the scope filtering logic end-to-end.

Tests:
1. Product ID extraction from file_path
2. Scope filter on synthetic search results
3. Partner scope service loads real product IDs from PekoPartnerDB
4. Over-fetch multiplier logic

Usage:
    venv/bin/python tests/test_scope_filter.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lightrag.operate import (
    _extract_product_ids_from_file_path,
    _is_in_scope,
    _apply_scope_filter,
)
from lightrag.base import QueryParam
from lightrag.services.partner_scope_service import (
    get_partner_scope_service,
    PARTNER_CONFIGS,
)


def test_extract_product_ids():
    print("=" * 60)
    print("Test 1: _extract_product_ids_from_file_path")
    print("=" * 60)

    # Single product
    fp = "product_id:67506658d2d30b7ee56ff9e1:source:product_batch_6637_item_1"
    ids = _extract_product_ids_from_file_path(fp)
    assert ids == {"67506658d2d30b7ee56ff9e1"}, f"Expected single ID, got {ids}"
    print(f"  ✅ Single product: {ids}")

    # Multi-product (SEP-joined)
    fp = "product_id:aaa111:source:batch_1<SEP>product_id:bbb222:source:batch_2<SEP>product_id:ccc333:source:batch_3"
    ids = _extract_product_ids_from_file_path(fp)
    assert ids == {"aaa111", "bbb222", "ccc333"}, f"Expected 3 IDs, got {ids}"
    print(f"  ✅ Multi-product: {ids}")

    # Empty / None
    assert _extract_product_ids_from_file_path("") == set()
    assert _extract_product_ids_from_file_path(None) == set()
    print(f"  ✅ Empty/None: returns empty set")

    # No product_id pattern
    fp = "some_random_file_path.txt"
    assert _extract_product_ids_from_file_path(fp) == set()
    print(f"  ✅ No product_id pattern: returns empty set")

    print()


def test_is_in_scope():
    print("=" * 60)
    print("Test 2: _is_in_scope")
    print("=" * 60)

    scope = {"aaa111", "bbb222"}

    # In scope (single)
    fp = "product_id:aaa111:source:batch_1"
    assert _is_in_scope(fp, scope) is True
    print(f"  ✅ Single product in scope")

    # In scope (multi, one matches)
    fp = "product_id:xxx999:source:batch_1<SEP>product_id:bbb222:source:batch_2"
    assert _is_in_scope(fp, scope) is True
    print(f"  ✅ Multi-product, one in scope")

    # Out of scope
    fp = "product_id:xxx999:source:batch_1<SEP>product_id:yyy888:source:batch_2"
    assert _is_in_scope(fp, scope) is False
    print(f"  ✅ Multi-product, none in scope")

    # No file_path
    assert _is_in_scope("", scope) is False
    print(f"  ✅ Empty file_path: not in scope (but filter keeps it as fail-open)")

    print()


def test_apply_scope_filter():
    print("=" * 60)
    print("Test 3: _apply_scope_filter")
    print("=" * 60)

    scope = {"aaa111aaa111aaa111aaa111", "bbb222bbb222bbb222bbb222"}

    search_result = {
        "final_entities": [
            {"entity_name": "E1", "file_path": "product_id:aaa111aaa111aaa111aaa111:source:b1"},
            {"entity_name": "E2", "file_path": "product_id:ccc333ccc333ccc333ccc333:source:b2"},
            {"entity_name": "E3", "file_path": "product_id:bbb222bbb222bbb222bbb222:source:b3<SEP>product_id:ccc333ccc333ccc333ccc333:source:b4"},
            {"entity_name": "E4"},  # No file_path — kept (fail-open)
        ],
        "final_relations": [
            {"src_id": "E1", "tgt_id": "E2", "file_path": "product_id:aaa111aaa111aaa111aaa111:source:b1"},
            {"src_id": "E2", "tgt_id": "E3", "file_path": "product_id:ccc333ccc333ccc333ccc333:source:b2"},
            {"src_id": "E1", "tgt_id": "E3"},  # No file_path — kept
        ],
        "vector_chunks": [
            {"chunk_id": "c1", "content": "...", "file_path": "product_id:aaa111aaa111aaa111aaa111:source:b1"},
            {"chunk_id": "c2", "content": "...", "file_path": "product_id:ccc333ccc333ccc333ccc333:source:b2"},
            {"chunk_id": "c3", "content": "...", "file_path": "product_id:bbb222bbb222bbb222bbb222:source:b3"},
        ],
        "chunk_tracking": {
            "c1": {"source": "C", "frequency": 1},
            "c2": {"source": "C", "frequency": 1},
            "c3": {"source": "C", "frequency": 1},
        },
        "query_embedding": [0.1, 0.2],
    }

    result = _apply_scope_filter(search_result, scope)

    # Entities: E1 (in scope), E3 (has prod_b in scope), E4 (no file_path, kept)
    assert len(result["final_entities"]) == 3, f"Expected 3 entities, got {len(result['final_entities'])}"
    entity_names = [e["entity_name"] for e in result["final_entities"]]
    assert entity_names == ["E1", "E3", "E4"], f"Expected E1,E3,E4, got {entity_names}"
    print(f"  ✅ Entities filtered: 4→3 ({entity_names})")

    # Relations: first (prod_a in scope), third (no file_path, kept)
    assert len(result["final_relations"]) == 2
    print(f"  ✅ Relations filtered: 3→2")

    # Chunks: c1 (prod_a), c3 (prod_b) — c2 (prod_c) removed
    assert len(result["vector_chunks"]) == 2
    chunk_ids = [c["chunk_id"] for c in result["vector_chunks"]]
    assert chunk_ids == ["c1", "c3"], f"Expected c1,c3, got {chunk_ids}"
    print(f"  ✅ Chunks filtered: 3→2 ({chunk_ids})")

    # Chunk tracking updated
    assert "c2" not in result["chunk_tracking"]
    assert "c1" in result["chunk_tracking"]
    assert "c3" in result["chunk_tracking"]
    print(f"  ✅ Chunk tracking cleaned up")

    # query_embedding preserved
    assert result["query_embedding"] == [0.1, 0.2]
    print(f"  ✅ Other fields preserved")

    print()


def test_query_param_scope():
    print("=" * 60)
    print("Test 4: QueryParam scope fields")
    print("=" * 60)

    # Default: no scope
    param = QueryParam()
    assert param.scope_product_ids is None
    assert param.scope_overfetch_multiplier == 3
    print(f"  ✅ Default: scope_product_ids=None, multiplier=3")

    # With scope
    param = QueryParam(
        scope_product_ids={"prod_a", "prod_b"},
        scope_overfetch_multiplier=5,
    )
    assert param.scope_product_ids == {"prod_a", "prod_b"}
    assert param.scope_overfetch_multiplier == 5
    print(f"  ✅ Custom scope: {len(param.scope_product_ids)} products, multiplier={param.scope_overfetch_multiplier}")

    # Over-fetch logic
    from copy import copy
    param = QueryParam(
        top_k=60,
        chunk_top_k=30,
        scope_product_ids={"a", "b"},
        scope_overfetch_multiplier=3,
    )
    effective = copy(param)
    m = param.scope_overfetch_multiplier
    effective.top_k = param.top_k * m
    effective.chunk_top_k = param.chunk_top_k * m
    assert effective.top_k == 180
    assert effective.chunk_top_k == 90
    print(f"  ✅ Over-fetch: top_k {param.top_k}→{effective.top_k}, chunk_top_k {param.chunk_top_k}→{effective.chunk_top_k}")

    print()


async def test_partner_scope_service():
    print("=" * 60)
    print("Test 5: PartnerScopeService (live MongoDB)")
    print("=" * 60)

    service = get_partner_scope_service()

    # Check configured partners
    partners = service.get_partner_ids()
    print(f"  Configured partners: {partners}")
    assert "peko" in partners
    print(f"  ✅ 'peko' is configured")

    # Unknown partner
    result = await service.get_scope_product_ids("unknown_partner")
    assert result is None
    print(f"  ✅ Unknown partner returns None")

    # Load Peko product IDs
    product_ids = await service.get_scope_product_ids("peko")
    assert product_ids is not None
    assert len(product_ids) > 4000
    print(f"  ✅ Peko scope loaded: {len(product_ids)} product IDs")

    # Verify some known IDs exist (from our earlier exploration)
    known_ids = [
        "62cfea73a10437da5c6c655d",  # SAP Concur
        "62cfea81a10437da5c6c65da",  # Mailchimp
        "62cfea85a10437da5c6c6601",  # Netskope
    ]
    for kid in known_ids:
        assert kid in product_ids, f"Expected {kid} in scope"
    print(f"  ✅ Known product IDs found in scope set")

    # Cache hit test
    import time
    start = time.time()
    product_ids_2 = await service.get_scope_product_ids("peko")
    cache_time = time.time() - start
    assert product_ids_2 == product_ids
    print(f"  ✅ Cache hit: {cache_time*1000:.1f}ms (same set returned)")

    # Verify against RAG store (Redis)
    try:
        import redis
        r = redis.from_url("redis://localhost:6380", decode_responses=True)
        in_rag = sum(1 for pid in product_ids if r.exists(f"lightRAG-v2_doc_status:{pid}"))
        r.close()
        print(f"  ✅ RAG coverage: {in_rag}/{len(product_ids)} ({100*in_rag/len(product_ids):.1f}%)")
    except Exception as e:
        print(f"  ⚠️  Redis check skipped: {e}")

    print()


def main():
    print("\n🔍 Testing Scope Filtering Implementation\n")

    test_extract_product_ids()
    test_is_in_scope()
    test_apply_scope_filter()
    test_query_param_scope()
    asyncio.run(test_partner_scope_service())

    print("=" * 60)
    print("All tests passed! ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
