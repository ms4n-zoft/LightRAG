#!/usr/bin/env python3
"""
Example: Product Ingestion with Web UI Monitoring

This example demonstrates how to ingest large datasets (8000+ records) from MongoDB
into LightRAG with real-time monitoring through the web UI.

The monitoring system integrates with LightRAG's existing pipeline status dialog,
allowing you to monitor progress without needing to watch terminal output.

Usage:
    python examples/product_ingestion_with_monitoring.py

Requirements:
    1. MongoDB running with product data
    2. LightRAG API server running (python -m lightrag.api.lightrag_server)
    3. Web UI accessible at http://localhost:9621
"""

from services.product_ingestion.models.config import IngestionConfig
from services.product_ingestion.core.service import ProductIngestionService
import asyncio
import logging
import sys
import os
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main example function"""
    print("🚀 Product Ingestion with Web UI Monitoring Example")
    print("=" * 60)

    # Configuration for your dataset
    config = IngestionConfig(
        batch_size=25,  # Adjust based on your system capacity
        working_dir="./enhanced_rag_100",  # Your LightRAG storage directory
        max_workers=3,  # Conservative concurrency
        enable_progress_tracking=True,
        enable_detailed_logging=True
    )

    # MongoDB connection details
    database = "product_db"  # Change to your database name
    collection = "products"  # Change to your collection name

    # Optional: Filter to process specific products
    filter_query = {
        # "status": "active",  # Uncomment to filter by status
        # "updated_on": {"$gte": "2024-01-01"}  # Uncomment to filter by date
    }

    # Optional: Limit for testing (remove for full dataset)
    limit = None  # Set to 100 for testing, None for full dataset

    print(f"📊 Configuration:")
    print(f"   Database: {database}")
    print(f"   Collection: {collection}")
    print(f"   Batch size: {config.batch_size}")
    print(f"   Working directory: {config.working_dir}")
    print(f"   Limit: {limit or 'None (full dataset)'}")
    print()

    # Initialize the service
    print("🔧 Initializing Product Ingestion Service...")
    service = ProductIngestionService(config)

    try:
        # Get collection statistics
        print("📈 Getting collection statistics...")
        stats = service.get_collection_stats(database, collection)
        total_docs = stats.get("count", 0)

        print(f"   Total documents in collection: {total_docs:,}")

        if limit:
            actual_limit = min(total_docs, limit)
            print(f"   Documents to process (limited): {actual_limit:,}")
        else:
            actual_limit = total_docs
            print(f"   Documents to process: {actual_limit:,}")

        estimated_batches = (
            actual_limit + config.batch_size - 1) // config.batch_size
        estimated_time = estimated_batches * 2  # Rough estimate: 2 seconds per batch

        print(f"   Estimated batches: {estimated_batches}")
        print(
            f"   Estimated time: {estimated_time // 60}m {estimated_time % 60}s")
        print()

        # Show sample product
        print("🔍 Sample product:")
        sample = service.get_sample_product(database, collection)
        if sample:
            print(f"   Product name: {sample.get('product_name', 'N/A')}")
            print(f"   Company: {sample.get('company', 'N/A')}")
            print(f"   Categories: {sample.get('categories', 'N/A')}")
        print()

        # Start ingestion with monitoring
        print("🚀 Starting product ingestion...")
        print("💡 Monitor progress in the web UI:")
        print("   1. Open http://localhost:9621 in your browser")
        print("   2. Go to the Documents tab")
        print("   3. Click 'Pipeline Status' button")
        print("   4. Watch real-time progress updates!")
        print()

        start_time = datetime.now()

        # Run the ingestion (this will integrate with the web UI monitoring)
        results = await service.ingest_products(
            database=database,
            collection=collection,
            filter_query=filter_query if filter_query else None,
            limit=limit
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Display results
        print("\n" + "=" * 60)
        print("🎉 INGESTION COMPLETED!")
        print("=" * 60)
        print(
            f"⏱️  Total time: {duration:.2f} seconds ({duration/60:.1f} minutes)")
        print(f"📊 Results:")
        print(f"   Status: {results['status']}")
        print(f"   Total products: {results['total_products']:,}")
        print(f"   Successfully processed: {results['total_processed']:,}")
        print(f"   Errors: {results['total_errors']:,}")
        print(
            f"   Success rate: {results['performance_metrics']['success_rate']:.1f}%")
        print(
            f"   Throughput: {results['performance_metrics']['products_per_second']:.2f} products/sec")

        # Show metadata insights
        metadata = results.get('metadata_summary', {})
        if metadata.get('categories'):
            print(f"\n📈 Top Categories:")
            top_categories = sorted(metadata['categories'].items(),
                                    key=lambda x: x[1], reverse=True)[:5]
            for category, count in top_categories:
                print(f"   {category}: {count}")

        if metadata.get('companies'):
            print(f"\n🏢 Top Companies:")
            top_companies = sorted(metadata['companies'].items(),
                                   key=lambda x: x[1], reverse=True)[:5]
            for company, count in top_companies:
                print(f"   {company}: {count}")

        # Show overall statistics
        overall_stats = metadata.get('overall_statistics', {})
        if overall_stats:
            print(f"\n📊 Overall Statistics:")
            if overall_stats.get('average_rating'):
                print(f"   Average rating: {overall_stats['average_rating']}")
            print(
                f"   Unique categories: {overall_stats.get('unique_categories', 0)}")
            print(
                f"   Unique companies: {overall_stats.get('unique_companies', 0)}")
            print(
                f"   Products with ratings: {overall_stats.get('products_with_ratings', 0):,}")

        print(f"\n✅ Your knowledge graph is ready for querying!")
        print(
            f"   You can now use the web UI or API to search your {results['total_processed']:,} products")

    except KeyboardInterrupt:
        print("\n⏹️  Ingestion interrupted by user")
    except Exception as e:
        print(f"\n❌ Ingestion failed: {e}")
        logger.exception("Detailed error information:")
    finally:
        # Clean up
        service.close()
        print("\n🔒 Resources cleaned up")


if __name__ == "__main__":
    # Check if we can import the required modules
    try:
        import pymongo
        print("✅ MongoDB client available")
    except ImportError:
        print("❌ PyMongo not installed. Install with: pip install pymongo")
        sys.exit(1)

    print("💡 Make sure you have:")
    print("   1. MongoDB running with your product data")
    print("   2. LightRAG API server running: python -m lightrag.api.lightrag_server")
    print("   3. Web UI accessible at http://localhost:9621")
    print()

    # Run the example
    asyncio.run(main())
