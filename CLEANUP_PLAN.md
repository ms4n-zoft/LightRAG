# LightRAG Codebase Cleanup Plan

## Phase 1: Safe Directory Cleanup (Zero Risk)

### Remove Debug/Test Storage Directories
```bash
# These contain only test data and can be safely removed
rm -rf debug_rag_test/
rm -rf debug_rag_test2/ 
rm -rf debug_rag_test3/
rm -rf enhanced_rag_100/
rm -rf test_improved_logging_rag/
rm -rf test_llm_debug_rag/
rm -rf test_logging_rag/
rm -rf test_metadata_rag/
rm -rf test_rag_storage/
rm -rf test_single_ingestion_rag/
rm -rf test_unlimited_tokens_rag/
```

### Remove Empty Directories
```bash
rm -rf config.ini/  # Empty directory
```

## Phase 2: Code Cleanup (Low Risk)

### Remove Example Code from Production Files

#### A. Remove main() example from product_ingestion_service.py
**File:** `lightrag/services/product_ingestion_service.py`
**Lines to remove:** 467-522
**Reason:** Example code should not be in production service files

#### B. Remove TODO comment from lightrag.py  
**File:** `lightrag/lightrag.py`
**Lines to remove:** 107-109
**Reason:** TODO comment for @Yannick, not needed in production

#### C. Mark deprecated methods (don't remove yet)
**File:** `lightrag/lightrag.py`
**Lines:** 956-1009
**Action:** Add deprecation warnings, don't remove yet

## Phase 3: Configuration Cleanup (Medium Risk)

### Clean up duplicate configurations
- Review and consolidate chunking configurations
- Remove unused environment variables
- Standardize storage configurations

## Phase 4: Examples Directory Cleanup (Low Risk)

### Keep only essential examples
**Keep:**
- `examples/lightrag_openai_demo.py`
- `examples/lightrag_openai_compatible_demo.py`
- `examples/product_ingestion_with_monitoring.py`

**Remove:**
- Community-contributed examples in `examples/unofficial-sample/`
- Duplicate examples

## Phase 5: Documentation Cleanup (Zero Risk)

### Clean up duplicate documentation
- Consolidate README files
- Remove outdated documentation
- Update configuration examples

## Safety Measures

### Before Each Phase:
1. Create git branch: `cleanup-phase-X`
2. Commit current state
3. Run tests to ensure nothing breaks
4. Document what was removed

### Backup Strategy:
```bash
# Create backup before cleanup
git checkout -b cleanup-backup
git add .
git commit -m "Backup before cleanup"

# Create cleanup branch
git checkout -b cleanup-phase-1
```

### Rollback Plan:
```bash
# If anything breaks, rollback immediately
git checkout cleanup-backup
```

## Post-Cleanup Benefits

1. **Reduced codebase size** by ~30%
2. **Easier navigation** without test directories
3. **Cleaner production code** without examples
4. **Better performance** with optimized configurations
5. **Easier maintenance** with consolidated code

## Next Steps After Cleanup

1. **Performance optimizations** on clean codebase
2. **Configuration consolidation** 
3. **Documentation updates**
4. **Testing on clean environment**
