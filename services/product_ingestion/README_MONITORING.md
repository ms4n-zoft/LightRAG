# Product Ingestion Web UI Monitoring

Monitor large batch processing jobs (8000+ records) through LightRAG's web interface instead of terminal output.

## 🌟 Features

- **Real-time Progress Tracking**: Watch batch processing progress in the web UI
- **ETA Calculations**: See estimated time remaining for large jobs
- **Detailed Status Messages**: Get insights into what's being processed
- **Error Reporting**: Track errors and success rates in real-time
- **Repositionable Dialog**: Move the monitoring dialog for optimal viewing
- **History Tracking**: Review processing history and messages

## 🚀 Quick Start

### 1. Start LightRAG API Server
```bash
python -m lightrag.api.lightrag_server --host 0.0.0.0 --port 9621
```

### 2. Open Web UI
Navigate to: http://localhost:9621

### 3. Run Product Ingestion with Monitoring
```python
from services.product_ingestion.core.service import ProductIngestionService
from services.product_ingestion.models.config import IngestionConfig

# Configure for your dataset
config = IngestionConfig(
    batch_size=25,
    working_dir="./enhanced_rag_100"
)

service = ProductIngestionService(config)

# This will automatically integrate with web UI monitoring
results = await service.ingest_products(
    database="your_db",
    collection="products",
    limit=8000  # Your large dataset
)
```

### 4. Monitor in Web UI
1. Go to **Documents** tab
2. Click **Pipeline Status** button
3. Watch real-time progress updates!

## 📊 Monitoring Dashboard

### Pipeline Status Dialog Features

**Progress Information:**
- Current batch / Total batches
- Percentage complete
- Estimated time remaining
- Processing speed (products/second)

**Status Indicators:**
- 🟢 Pipeline Busy: Shows when processing is active
- 🟢 Request Pending: Shows when requests are queued
- ⏰ Job Start Time: When the current job began
- 📝 Job Name: Descriptive name of the current operation

**Live Messages:**
- Latest status message with timestamp
- Processing updates for each batch
- Error notifications
- Completion summaries

**Message History:**
- Scrollable history of all processing messages
- Auto-scroll to latest messages
- Manual scroll to review previous activity
- Limited to 1000 messages for performance

### Dialog Positioning
The monitoring dialog can be positioned:
- **Left**: For side-by-side monitoring
- **Center**: Default centered view  
- **Right**: Alternative side positioning

## 🔧 Integration Details

### How It Works

The monitoring system integrates with LightRAG's existing pipeline status infrastructure:

1. **Pipeline Status Integration**: Uses LightRAG's shared storage system for status updates
2. **Real-time Updates**: Web UI polls status every 2 seconds
3. **Background Processing**: Jobs run as background tasks
4. **Error Handling**: Graceful error reporting and recovery

### Monitoring Components

```python
# Core monitoring class
from services.product_ingestion.monitoring import PipelineStatusIntegrator

# Usage in your service
integrator = await get_pipeline_integrator()

async with integrator.monitor_job("My Job", total_records=8000) as monitor:
    for batch_id in range(1, total_batches + 1):
        await monitor.update_progress(batch_id, "Processing batch...")
        # ... process batch ...
        await monitor.report_batch_results(results)
```

## 📈 Performance Monitoring

### Metrics Tracked
- **Throughput**: Products processed per second
- **Batch Timing**: Average time per batch
- **Success Rate**: Percentage of successfully processed products
- **Error Analysis**: Breakdown of error types and frequencies

### Large Dataset Optimization
For 8000+ record datasets:
- **Batch Size**: Default 25 (adjustable based on system capacity)
- **Memory Management**: Optional cache clearing between batches
- **Progress Tracking**: Efficient status updates without performance impact
- **Error Recovery**: Continue processing even if individual batches fail

## 🛠️ Configuration Options

### Ingestion Config
```python
config = IngestionConfig(
    batch_size=25,              # Products per batch
    max_workers=3,              # Concurrent processing threads
    working_dir="./storage",    # LightRAG storage directory
    enable_progress_tracking=True,  # Enable web UI monitoring
    clear_cache_after_batch=True,   # Memory optimization
    max_memory_usage_mb=2048    # Memory limit (2GB)
)
```

### Monitoring Config
```python
# Customize job monitoring
async with integrator.monitor_job(
    job_name="Product Ingestion - RFP Dataset",
    total_records=8000,
    batch_size=25
) as monitor:
    # Custom progress updates
    await monitor.update_progress(
        batch_id=42, 
        message="Processing high-value products",
        custom_data={"category": "Enterprise Software"}
    )
```

## 🔍 Monitoring Examples

### Basic Monitoring
```python
# Simple progress tracking
await monitor.update_progress(batch_id, "Processing batch 42/320")
```

### Detailed Batch Reporting
```python
# Report detailed batch results
batch_results = {
    "batch_id": 42,
    "processed": 23,
    "errors": 2,
    "duration_seconds": 1.5,
    "metadata_summary": {...}
}
await monitor.report_batch_results(batch_results)
```

### Custom Messages
```python
# Add custom status messages
await monitor.add_message("🎯 Processing high-priority products")
await monitor.add_message("⚠️  Detected data quality issues in batch 15")
await monitor.add_message("✅ Knowledge graph updated successfully")
```

## 🚨 Error Monitoring

### Error Types Tracked
- **ValidationError**: Missing required fields
- **MetadataExtractionError**: Failed to extract product metadata
- **NormalizationError**: Text processing failures
- **LightRAGInsertionError**: Knowledge graph insertion failures

### Error Reporting
```python
# Errors are automatically reported to the monitoring system
{
    "batch_id": 42,
    "errors": [
        {
            "product_index": 5,
            "product_id": "prod_12345",
            "product_name": "Salesforce CRM",
            "error": "Missing product_name field",
            "error_type": "ValidationError"
        }
    ]
}
```

## 📱 Mobile Monitoring

The web UI is responsive and works on mobile devices:
- **Tablet**: Full monitoring experience
- **Phone**: Condensed view with essential metrics
- **Touch**: Tap to reposition dialog, scroll through history

## 🔧 Troubleshooting

### Common Issues

**Monitoring Not Working:**
- Ensure LightRAG API server is running
- Check that web UI is accessible
- Verify MongoDB connection

**Slow Updates:**
- Check system resources (CPU, memory)
- Reduce batch size if needed
- Enable cache clearing between batches

**Memory Issues:**
- Set `max_memory_usage_mb` limit
- Enable `clear_cache_after_batch`
- Monitor system resources during processing

### Debug Mode
```python
# Enable detailed logging
import logging
logging.getLogger("services.product_ingestion").setLevel(logging.DEBUG)

# Check monitoring integration
integrator = await get_pipeline_integrator()
print(f"Monitoring initialized: {integrator._initialized}")
```

## 🎯 Best Practices

### For Large Datasets (8000+ records)
1. **Start Small**: Test with 100-500 records first
2. **Monitor Resources**: Watch CPU, memory, and disk usage
3. **Batch Sizing**: Start with 25, adjust based on performance
4. **Error Handling**: Review error patterns and fix data issues
5. **Progress Tracking**: Use web UI instead of terminal monitoring

### Production Deployment
1. **Resource Limits**: Set appropriate memory and CPU limits
2. **Error Recovery**: Implement retry logic for transient failures
3. **Monitoring Alerts**: Set up alerts for high error rates
4. **Performance Tuning**: Optimize batch size based on system capacity

## 📚 API Reference

### Pipeline Status Endpoints
- `GET /documents/pipeline_status`: Get current pipeline status
- `POST /product_ingestion/start`: Start monitored ingestion job
- `GET /product_ingestion/jobs`: List all ingestion jobs

### Monitoring Classes
- `PipelineStatusIntegrator`: Main monitoring integration
- `JobMonitor`: Individual job progress tracking
- `ProductIngestionService`: Enhanced with monitoring support

## 🤝 Contributing

To extend the monitoring system:

1. **Add New Metrics**: Extend `JobMonitor.update_progress()`
2. **Custom Messages**: Use `monitor.add_message()` for custom updates
3. **Error Types**: Add new error categories in batch processor
4. **UI Enhancements**: Modify the web UI pipeline status dialog

## 📄 License

This monitoring system is part of the LightRAG project and follows the same license terms.
