# Post-Ingestion RAG Usage Guide

After successfully ingesting your product database using the Product Ingestion Service, you can leverage powerful RAG (Retrieval-Augmented Generation) capabilities for both RFP generation and semantic search.

## 🎯 Available Query Endpoints

### General Query Endpoints
- **`/query`** - Standard query with full response generation
- **`/query/stream`** - Streaming query for real-time responses  
- **`/query/data`** - Raw data retrieval (entities, relationships, chunks)

### Query Modes for Different Use Cases

#### For RFP Generation:
- **`"hybrid"`** - Combines local entities + global relationships (perfect for RFPs)
- **`"mix"`** - Integrates knowledge graph + vector retrieval (comprehensive)
- **`"global"`** - Focuses on relationships between entities

#### For Semantic Search:
- **`"local"`** - Entity-focused semantic similarity search
- **`"naive"`** - Pure vector similarity search

## 🚀 What Happens After Ingesting 8,000 Products

Once you ingest your 8,000 products, the system creates a comprehensive knowledge graph:

```
📊 Your 8,000 products become:
├── 🏢 Company entities (Salesforce, Microsoft, etc.)
├── 📱 Product entities (CRM systems, databases, etc.)  
├── 🏷️ Category entities (SaaS, Enterprise Software, etc.)
├── 🔗 Relationships (company-makes-product, product-belongs-to-category)
└── 📄 Text chunks (product descriptions, features, reviews)
```

## 📋 Query Examples

### RFP Generation Queries

Use **hybrid mode** for complex business requirements:

```javascript
// Complex enterprise requirements
const rfpResponse = await queryText({
  query: "I need a CRM system for a large enterprise with 500+ users, must integrate with Salesforce and have advanced reporting",
  mode: "hybrid",  // Best for complex requirements
  response_type: "Multiple Paragraphs",
  top_k: 20
})

// Industry-specific requirements
const industryResponse = await queryText({
  query: "Find CRM solutions for financial services with compliance features and audit trails",
  mode: "hybrid",
  response_type: "Bullet Points",
  top_k: 15
})

// Technical requirements
const techResponse = await queryText({
  query: "Enterprise collaboration tools with SSO, security certifications, and API integration",
  mode: "mix",
  response_type: "Multiple Paragraphs",
  top_k: 25
})
```

### Semantic Search Queries

Use **local mode** for similarity-based searches:

```javascript
// Find similar products
const similarResponse = await queryText({
  query: "project management software similar to Asana with time tracking",
  mode: "local",  // Best for similarity search
  top_k: 10
})

// Feature-based search
const featureResponse = await queryText({
  query: "business intelligence platforms with real-time dashboards",
  mode: "local",
  top_k: 12
})

// Category exploration
const categoryResponse = await queryText({
  query: "cloud databases that support multi-region deployment and backup",
  mode: "mix",
  top_k: 15
})
```

## 🔧 Specialized Query Methods

Your Product Ingestion Service includes dedicated query methods:

```python
from services.product_ingestion.core.service import ProductIngestionService

# Initialize service (after ingestion is complete)
service = ProductIngestionService(config)

# RFP-optimized queries
rfp_result = await service.query_for_rfp(
    "Find enterprise software solutions for digital transformation with cloud migration support"
)

# Semantic similarity searches  
semantic_result = await service.semantic_search(
    "Products similar to Microsoft Teams for remote collaboration"
)

# Custom queries with specific modes
custom_result = await service.custom_query(
    "Compare top 5 CRM platforms for small business",
    mode="hybrid",
    top_k=5
)
```

## 📊 Query Capabilities

### Knowledge Graph Queries
- **Entity relationships** - "Which companies make CRM software?"
- **Product comparisons** - "Compare Salesforce vs HubSpot features"
- **Category analysis** - "All enterprise software with integration capabilities"

### Vector Similarity Queries
- **Semantic matching** - Find products by description similarity
- **Feature matching** - Products with similar functionality  
- **Use case matching** - Solutions for similar business problems

## 💡 Recommended Query Strategies

### For RFP Generation:
1. **Use `"hybrid"` mode** for complex, multi-faceted requirements
2. **Set `response_type: "Multiple Paragraphs"`** for detailed responses
3. **Use higher `top_k` values (20-50)** for comprehensive results
4. **Include specific constraints** in your query (budget, user count, compliance needs)

Example RFP Query Structure:
```javascript
{
  query: "[Business context] + [Specific requirements] + [Constraints] + [Integration needs]",
  mode: "hybrid",
  response_type: "Multiple Paragraphs", 
  top_k: 25,
  max_total_tokens: 4000
}
```

### For Semantic Search:
1. **Use `"local"` mode** for similarity-based searches
2. **Use `"mix"` mode** for combining graph + vector search
3. **Use lower `top_k` values (5-15)** for focused results
4. **Be specific about features** you're looking for

Example Semantic Search Structure:
```javascript
{
  query: "[Product type] + [Key features] + [Similar to existing product]",
  mode: "local",
  top_k: 10,
  chunk_top_k: 20
}
```

## 🎯 Advanced Query Features

### Streaming Queries
For real-time responses during complex analysis:

```javascript
await queryTextStream({
  query: "Comprehensive analysis of project management tools for agile development teams",
  mode: "hybrid",
  response_type: "Multiple Paragraphs"
}, 
onChunk: (chunk) => console.log(chunk),
onError: (error) => console.error(error)
)
```

### Data-Only Queries
To get raw structured data without LLM generation:

```javascript
const rawData = await queryData({
  query: "CRM software companies",
  mode: "hybrid",
  top_k: 20
})

// Returns: { entities: [...], relationships: [...], chunks: [...], metadata: {...} }
```

### Conversation Context
For follow-up queries with context:

```javascript
const followUpResponse = await queryText({
  query: "What about their pricing models?",
  mode: "hybrid",
  conversation_history: [
    { role: "user", content: "Tell me about enterprise CRM solutions" },
    { role: "assistant", content: "Here are the top enterprise CRM solutions..." }
  ],
  history_turns: 1
})
```

## 🔍 Query Use Case Examples

### Enterprise Software Selection
```javascript
// Multi-criteria software evaluation
const evaluation = await queryText({
  query: `
    I need to select an enterprise resource planning (ERP) system for a manufacturing company with:
    - 1000+ employees across 5 locations
    - Integration with existing inventory management
    - Real-time reporting and analytics
    - Compliance with SOX regulations
    - Budget under $500K annually
  `,
  mode: "hybrid",
  response_type: "Multiple Paragraphs",
  top_k: 30
})
```

### Competitive Analysis
```javascript
// Compare competing solutions
const comparison = await queryText({
  query: "Compare the top 3 customer support platforms: features, pricing, integration capabilities, and user reviews",
  mode: "mix",
  response_type: "Bullet Points",
  top_k: 20
})
```

### Technology Stack Recommendations
```javascript
// Complete technology stack suggestions
const stackRecommendation = await queryText({
  query: "Recommend a complete technology stack for a fintech startup: database, API management, security, monitoring, and compliance tools",
  mode: "hybrid",
  response_type: "Multiple Paragraphs",
  top_k: 40
})
```

## ⚡ Performance Tips

### Optimize Query Performance:
1. **Use appropriate `top_k` values** - Higher values = more comprehensive but slower
2. **Leverage `chunk_top_k`** for fine-tuning text retrieval
3. **Set `max_total_tokens`** to control response length and processing time
4. **Use specific query language** - More specific queries = better results

### Token Management:
```javascript
// Efficient token usage for large queries
const optimizedQuery = await queryText({
  query: "Enterprise software recommendations",
  mode: "hybrid",
  max_entity_tokens: 1000,
  max_relation_tokens: 1000,
  max_total_tokens: 3000,
  top_k: 15
})
```

## 🚀 Getting Started

1. **Complete Product Ingestion** - Ensure all 8,000+ products are successfully ingested
2. **Test Basic Queries** - Start with simple semantic searches
3. **Experiment with Modes** - Try different query modes for your use cases
4. **Refine Parameters** - Adjust `top_k`, `response_type`, and other parameters
5. **Build Applications** - Integrate queries into your RFP and search workflows

## 📚 API Reference

For complete API documentation, see:
- `/docs` - Interactive API documentation
- Query Routes: `/query`, `/query/stream`, `/query/data`
- Product Ingestion Routes: `/product_ingestion/*`

---

**Note**: This guide assumes you have successfully completed the product ingestion process using the Product Ingestion Service. The quality and relevance of query results depend on the completeness and accuracy of your ingested product data.
