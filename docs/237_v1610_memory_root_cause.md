# V1.6.10 Memory Root Cause

Timeline status: `V1610_MEMORY_TIMELINE_ANALYSIS_COMPLETE`
Root cause status: `V22_TRAINING_MEMORY_ROOT_CAUSE_CONFIRMED`
- root_causes: `ROOT_CAUSE_MEMORY_SENTINEL_FALSE_POSITIVE, ROOT_CAUSE_TRANSIENT_GLOBAL_FREE_MEMORY_DIP, ROOT_CAUSE_REAL_CAPACITY_LIMIT`
- allocated_growth_mb: `14.91`
- reserved_growth_mb: `0.0`
- minimum_logged_free_mb_before_stop: `241`
- The old stop condition was a single global free-memory sample, not a sustained post-cleanup signal.
- PyTorch tensor leak, validation retention, and checkpoint retention are not confirmed from v1.6.9 logs.
