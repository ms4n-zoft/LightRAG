# MongoDB to Redis Migration Schema Analysis

## Overview
This document analyzes the schema differences between MongoDB and Redis implementations for LightRAG's KV storage and Doc Status storage systems.

## 1. LIGHTRAG_KV_STORAGE Schema Analysis

### MongoDB Implementation (MongoKVStorage)
- **Storage Structure**: Uses MongoDB collections
- **Key Format**: Uses `_id` field as the primary key
- **Data Format**: BSON documents
- **Namespace Handling**: 
  - Collection name = `{workspace}_{namespace}`
  - Example: `workspace1_text_chunks`

### Redis Implementation (RedisKVStorage)
- **Storage Structure**: Uses Redis key-value pairs
- **Key Format**: `{final_namespace}:{document_id}`
- **Data Format**: JSON strings
- **Namespace Handling**:
  - Key prefix = `{workspace}_{namespace}`
  - Example: `workspace1_text_chunks:doc_123`

### Key Differences

| Aspect | MongoDB | Redis |
|--------|---------|-------|
| **Key Structure** | `_id` field | `{namespace}:{id}` prefix |
| **Data Format** | BSON | JSON string |
| **Storage Method** | Collections | Key-value pairs |
| **Query Capability** | Complex queries, aggregation | Simple key lookups |
| **Indexing** | Built-in indexes | No indexes (key-based) |

## 2. LIGHTRAG_DOC_STATUS_STORAGE Schema Analysis

### Document Structure (DocProcessingStatus)
Both implementations use the same data structure:

```python
@dataclass
class DocProcessingStatus:
    content_summary: str          # First 100 chars of document content
    content_length: int           # Total length of document
    file_path: str               # File path of the document
    status: DocStatus            # Current processing status
    created_at: str              # ISO format timestamp
    updated_at: str              # ISO format timestamp
    track_id: str | None         # Tracking ID for monitoring
    chunks_count: int | None     # Number of chunks after splitting
    chunks_list: list[str]       # List of chunk IDs
    error_msg: str | None        # Error message if failed
    metadata: dict[str, Any]     # Additional metadata
```

### MongoDB Implementation (MongoDocStatusStorage)
- **Storage**: MongoDB collection
- **Key**: `_id` field
- **Data Migration**: Includes `_prepare_doc_status_data()` method for backward compatibility
- **Special Handling**:
  - Migrates legacy `error` field to `error_msg`
  - Ensures `chunks_list` is always an array
  - Sets default values for missing fields

### Redis Implementation (RedisDocStatusStorage)
- **Storage**: Redis key-value pairs
- **Key Format**: `{final_namespace}:{doc_id}`
- **Data Format**: JSON string
- **Special Handling**:
  - Same field validation as MongoDB
  - Ensures `chunks_list` is always an array
  - Uses SCAN for iteration (no native indexing)

## 3. Namespace Types

### KV Storage Namespaces
1. **`text_chunks`** - Document chunks with metadata
2. **`full_docs`** - Complete documents
3. **`full_entities`** - Extracted entities
4. **`full_relations`** - Extracted relationships
5. **`llm_response_cache`** - LLM response caching

### Doc Status Namespace
1. **`doc_status`** - Document processing status

## 4. Data Migration Requirements

### Field Mappings
| MongoDB Field | Redis Field | Notes |
|---------------|-------------|-------|
| `_id` | Key prefix | MongoDB `_id` becomes Redis key suffix |
| All other fields | Same | Direct field mapping |
| `create_time` | `create_time` | Unix timestamp |
| `update_time` | `update_time` | Unix timestamp |

### Special Considerations

#### Text Chunks Namespace
- **MongoDB**: Ensures `llm_cache_list` field exists
- **Redis**: Same validation
- **Migration**: Direct field copy

#### Doc Status Namespace
- **MongoDB**: Handles legacy `error` → `error_msg` migration
- **Redis**: Same migration logic
- **Migration**: Apply same field transformations

## 5. Migration Strategy

### Data Transformation Steps
1. **Extract** documents from MongoDB collections
2. **Transform** MongoDB `_id` to Redis key format
3. **Validate** field compatibility
4. **Load** into Redis with proper key structure

### Key Format Conversion
```
MongoDB: {collection: "workspace_text_chunks", _id: "doc_123"}
Redis:   {key: "workspace_text_chunks:doc_123", value: "{...json...}"}
```

### Batch Processing
- Process collections in batches to avoid memory issues
- Use Redis pipelines for efficient bulk operations
- Implement retry logic for failed operations

## 6. Compatibility Matrix

| Feature | MongoDB | Redis | Migration Impact |
|---------|---------|-------|------------------|
| **Basic CRUD** | ✅ | ✅ | Low - Direct mapping |
| **Batch Operations** | ✅ | ✅ | Low - Pipeline support |
| **Field Validation** | ✅ | ✅ | Low - Same logic |
| **Timestamp Handling** | ✅ | ✅ | Low - Same format |
| **Complex Queries** | ✅ | ❌ | High - Requires application-level filtering |
| **Indexing** | ✅ | ❌ | Medium - Redis uses key-based access |

## 7. Migration Script Requirements

### Input Requirements
- Source MongoDB URI and database
- Destination Redis URI
- Workspace configuration
- Collection/namespace mapping

### Output Validation
- Document count verification
- Field structure validation
- Key format verification
- Data integrity checks

### Error Handling
- Retry logic for network issues
- Partial failure recovery
- Data validation errors
- Rollback capabilities

## Conclusion

The MongoDB to Redis migration is **highly compatible** with minimal schema changes required. The main differences are:

1. **Key Structure**: MongoDB `_id` → Redis `{namespace}:{id}`
2. **Data Format**: BSON → JSON string
3. **Storage Method**: Collections → Key-value pairs
4. **Query Capability**: Complex queries → Key-based lookups

The migration can be performed with high confidence as both implementations use the same data structures and validation logic.
