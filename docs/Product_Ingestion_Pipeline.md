# Product Ingestion Pipeline Design

## Overview
Optimized ingestion pipeline for **RFP generation** and **semantic search** over 8,000+ product records.

## Architecture Choices

### Data Flow
```
MongoDB Products → Normalization → LightRAG → Neo4j KG + Qdrant Vectors
```

### Key Components
- **Source**: MongoDB product collection
- **Processing**: Batch normalization with metadata extraction
- **Storage**: Neo4j (knowledge graph) + Qdrant (embeddings)
- **LLM**: OpenAI GPT-4o-mini
- **Embeddings**: Azure OpenAI (3072-dim)

## Use Case Optimizations

### 1. RFP Generation (Complex Multi-factor Analysis)
**Query Mode**: `hybrid` (KG + vector search)

**Optimizations**:
- Rich entity extraction from structured product text
- Relationship modeling: Product ↔ Brand, Category, Features, Specs
- Metadata categorization for filtering (price ranges, rating tiers)
- Context-aware text formatting for LLM reasoning

**Example Entities & Relationships**:
```
Product(iPhone 15) --MANUFACTURED_BY--> Brand(Apple)
Product(iPhone 15) --BELONGS_TO--> Category(Electronics)
Product(iPhone 15) --HAS_FEATURE--> Feature(Face ID)
Product(iPhone 15) --PRICED_AT--> Price($799)
```

### 2. Semantic Search (Direct Product Matching)
**Query Mode**: `local` (vector similarity)

**Optimizations**:
- Dense product descriptions with feature keywords
- Specification details embedded for technical queries
- Brand and category context for disambiguation
- Direct text-to-vector matching without graph traversal

## Data Normalization Strategy

### Input (Raw JSON)
```json
{
  "_id": "...",
  "name": "Product Name",
  "category": "Electronics",
  "features": ["Feature 1", "Feature 2"],
  "specifications": [{"name": "RAM", "value": "16GB"}]
}
```

### Output (Structured Text)
```
Product Information:
Name: Product Name
Category: Electronics
Brand: Apple
Price: $799.00

Product Description:
[Original description with context]

Key Features:
1. Feature 1
2. Feature 2

Technical Specifications:
- RAM: 16GB
- Storage: 512GB

Product Context:
This electronics product is manufactured by Apple and is currently available.
With a customer rating of 4.5/5.0, it represents a premium option in the electronics market segment.
```

### Metadata Extraction
```python
ProductMetadata(
    product_id="...",
    category="Electronics",
    brand="Apple", 
    price_range="premium",    # budget|mid-range|premium|luxury
    rating_tier="excellent",  # excellent|good|average|poor
    availability="available"
)
```

## Processing Pipeline

### Batch Processing
- **Batch Size**: 50 products (memory optimization)
- **Parallel Workers**: 5 (I/O concurrency)
- **Error Handling**: Continue on individual product failures

### Text Chunking
- **Chunk Size**: 1000 tokens (optimal for embeddings)
- **Overlap**: 200 tokens (context preservation)
- **Strategy**: Semantic boundaries (product boundaries)

### Knowledge Graph Construction
- **Automatic**: LightRAG extracts entities and relationships from structured text
- **Schema-free**: Adapts to product variations
- **Persistent**: Neo4j provides ACID storage

## Query Optimization

### RFP Queries (Complex)
```python
# Uses hybrid mode: KG reasoning + vector similarity
result = rag.query(
    "Office setup under $5000 with high ratings",
    param=QueryParam(mode="hybrid")
)
```
- Leverages price categorization metadata
- Uses rating tier filtering
- Combines multiple product relationships
- Provides reasoning chains

### Semantic Search (Direct)
```python
# Uses local mode: Pure vector similarity
result = rag.query(
    "wireless bluetooth headphones",
    param=QueryParam(mode="local")
)
```
- Direct embedding similarity
- Fast response times
- Feature-based matching
- No graph traversal overhead

## Performance Characteristics

### Ingestion
- **Throughput**: ~100 products/minute
- **Memory**: ~2GB peak (batch processing)
- **Storage**: ~1MB per 100 products (compressed)

### Query Performance
- **RFP (hybrid)**: 2-5 seconds (complex reasoning)
- **Search (local)**: 0.5-1 second (vector lookup)
- **Concurrent**: 10+ queries/second

## Scaling Considerations

### Current Limits (8K products)
- **Qdrant**: 1GB free tier (sufficient for 3072-dim embeddings)
- **Neo4j**: Free Aura instance (handles relationship complexity)
- **MongoDB**: Standard connection pooling

### Growth Path
- **Incremental Updates**: Filter by timestamp/ID for new products
- **Partitioning**: Category-based collections for >100K products
- **Caching**: Query result caching for common RFP patterns

## Key Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Structured text over raw JSON | Better entity extraction | Larger storage |
| Hybrid mode for RFP | Complex reasoning needs | Slower queries |
| Local mode for search | Speed over complexity | Less context |
| Batch processing | Memory efficiency | Longer ingestion |
| Rich metadata | Advanced filtering | Processing overhead |

## Usage Patterns

### Development
```bash
# Test with 10 products
python scripts/setup_product_ingestion.py

# Full ingestion
service.ingest_products(db="products", collection="items", limit=None)
```

### Production Queries
```python
# RFP generation
rfp_result = await service.query_for_rfp(
    "Budget office setup with ergonomic features under $2000"
)

# Product search  
search_result = await service.semantic_search(
    "gaming laptop with RTX graphics"
)
```

This pipeline balances complexity (RFP) with speed (search) while maintaining data quality and system performance.
