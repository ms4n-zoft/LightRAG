#!/usr/bin/env python3
"""
Setup and test script for Product Ingestion Service

This script helps you:
1. Update environment variables with neo4j+ssc:// scheme
2. Test all service connections
3. Run a sample ingestion
4. Test RFP and semantic search queries
"""

from services.product_ingestion_service import ProductIngestionService, IngestionConfig
from dotenv import load_dotenv
import os
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import services
sys.path.append(str(Path(__file__).parent.parent))


load_dotenv()


def update_env_file():
    """Update .env file with correct Neo4j scheme"""
    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        print("❌ .env file not found")
        return False

    # Read current content
    with open(env_path, 'r') as f:
        content = f.read()

    # Update Neo4j URI scheme
    updated_content = content.replace(
        "NEO4J_URI=neo4j+s://b4accc6a.databases.neo4j.io",
        "NEO4J_URI=neo4j+ssc://b4accc6a.databases.neo4j.io"
    )

    # Write back if changed
    if content != updated_content:
        with open(env_path, 'w') as f:
            f.write(updated_content)
        print("✅ Updated .env with neo4j+ssc:// scheme")
        return True
    else:
        print("✅ .env already has correct Neo4j scheme")
        return True


async def test_service_setup():
    """Test the ingestion service setup"""
    print("🔧 Testing Product Ingestion Service Setup...")

    try:
        # Test service initialization
        config = IngestionConfig(
            batch_size=5,  # Small batch for testing
            working_dir="./test_product_rag"
        )

        service = ProductIngestionService(config)
        print("✅ Service initialized successfully")

        # Test RAG initialization
        rag = await service.initialize_rag()
        print("✅ LightRAG initialized successfully")

        # Test product fetching (without actually fetching)
        print("✅ MongoDB connection tested during service init")

        return service

    except Exception as e:
        print(f"❌ Service setup failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def run_sample_ingestion(service: ProductIngestionService):
    """Run a sample ingestion with a few products"""
    print("\n📦 Running Sample Ingestion...")

    # You'll need to replace these with your actual database details
    database_name = input("Enter your MongoDB database name: ").strip()
    collection_name = input(
        "Enter your collection name (default: products): ").strip() or "products"

    try:
        # Test with a small limit first
        results = await service.ingest_products(
            database=database_name,
            collection=collection_name,
            limit=10  # Just 10 products for testing
        )

        print(f"\n🎉 Sample Ingestion Results:")
        print(f"  - Total processed: {results['total_processed']}")
        print(f"  - Total errors: {results['total_errors']}")
        print(f"  - Duration: {results['duration_seconds']:.2f}s")

        if results['metadata_summary']['categories']:
            print(f"\n📊 Categories found:")
            for category, count in results['metadata_summary']['categories'].items():
                print(f"    - {category}: {count}")

        return results['total_processed'] > 0

    except Exception as e:
        print(f"❌ Sample ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_queries(service: ProductIngestionService):
    """Test RFP and semantic search queries"""
    print("\n🔍 Testing Query Capabilities...")

    try:
        # Test RFP query
        print("\n1. Testing RFP Query (Hybrid Mode):")
        rfp_query = """
        I need to create a proposal for office equipment that includes:
        - Budget-friendly options under $500
        - High customer ratings (4+ stars)
        - Currently available products
        - Mix of electronics and furniture
        
        Please provide detailed recommendations with justifications.
        """

        rfp_result = await service.query_for_rfp(rfp_query)
        print("RFP Result:")
        print("-" * 60)
        print(rfp_result)
        print("-" * 60)

        # Test semantic search
        print("\n2. Testing Semantic Search (Local Mode):")
        search_queries = [
            "wireless bluetooth headphones",
            "ergonomic office chair",
            "laptop computer for business"
        ]

        for query in search_queries:
            print(f"\nQuery: '{query}'")
            search_result = await service.semantic_search(query)
            print("Result:")
            print("-" * 40)
            print(
                search_result[:300] + "..." if len(search_result) > 300 else search_result)
            print("-" * 40)

    except Exception as e:
        print(f"❌ Query testing failed: {e}")
        import traceback
        traceback.print_exc()


def print_usage_guide():
    """Print usage guide for the service"""
    print("""
🎯 PRODUCT INGESTION SERVICE USAGE GUIDE

1. ENVIRONMENT SETUP:
   - Ensure all services are configured in .env
   - Neo4j should use neo4j+ssc:// scheme
   - MongoDB credentials for both LightRAG and product source

2. INGESTION PROCESS:
   ```python
   from services.product_ingestion_service import ProductIngestionService, IngestionConfig
   
   # Configure service
   config = IngestionConfig(
       batch_size=50,           # Products per batch
       working_dir="./rag_storage",
       max_workers=5            # Parallel processing
   )
   
   service = ProductIngestionService(config)
   
   # Ingest products
   results = await service.ingest_products(
       database="your_db",
       collection="products",
       limit=1000  # Optional limit
   )
   ```

3. QUERY USAGE:

   RFP Generation (Complex Analysis):
   ```python
   rfp_result = await service.query_for_rfp(
       "I need products for a $5000 budget office setup with modern design"
   )
   ```
   
   Semantic Search (Direct Matching):
   ```python
   search_result = await service.semantic_search(
       "wireless keyboard with backlight"
   )
   ```

4. QUERY MODES EXPLAINED:
   - RFP (hybrid): Uses knowledge graph + embeddings for complex reasoning
   - Semantic (local): Direct vector similarity for product matching
   - Global: High-level summaries and themes
   - Naive: Simple text matching

5. METADATA BENEFITS:
   - Automatic categorization by price range, rating tier
   - Rich product context for entity extraction
   - Structured text for optimal knowledge graph construction
   
6. SCALING CONSIDERATIONS:
   - Start with small batches (20-50 products)
   - Monitor memory usage during ingestion
   - Use filters for incremental updates
   - Neo4j provides persistent graph storage
""")


async def main():
    """Main setup and testing workflow"""
    print("🚀 LightRAG Product Ingestion Setup")
    print("=" * 50)

    # Step 1: Update environment
    print("\n1. Updating Environment Configuration...")
    update_env_file()

    # Step 2: Test service setup
    print("\n2. Testing Service Setup...")
    service = await test_service_setup()

    if not service:
        print("❌ Service setup failed. Please check your configuration.")
        return

    # Step 3: Ask user what they want to do
    print("\n3. Choose next steps:")
    print("   a) Run sample ingestion (10 products)")
    print("   b) Skip to usage guide")
    print("   c) Exit")

    choice = input("\nEnter choice (a/b/c): ").strip().lower()

    if choice == 'a':
        success = await run_sample_ingestion(service)
        if success:
            await test_queries(service)
    elif choice == 'b':
        pass
    else:
        print("👋 Exiting...")
        return

    # Always show usage guide
    print_usage_guide()

    print("\n✨ Setup complete! You can now use the ProductIngestionService.")


if __name__ == "__main__":
    asyncio.run(main())
