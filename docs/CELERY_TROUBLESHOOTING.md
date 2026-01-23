# Celery Worker Troubleshooting

## SIGSEGV (Segmentation Fault) on macOS

### Problem
Celery workers crash with `signal 11 (SIGSEGV)` errors when using the default `prefork` pool on macOS, especially with Python 3.14+.

### Symptoms
```
ERROR/MainProcess] Process 'ForkPoolWorker-1' pid:15023 exited with 'signal 11 (SIGSEGV)'
WorkerLostError: Worker exited prematurely: signal 11 (SIGSEGV)
```

### Solution

#### Option 1: Use Solo Pool (Recommended for macOS Development)
```bash
celery -A core worker --loglevel=info --pool=solo
```

**Pros:**
- No forking, avoids SIGSEGV
- Simple and reliable
- Good for development

**Cons:**
- Single process (no concurrency)
- Not suitable for high-load production

#### Option 2: Use Threads Pool
```bash
celery -A core worker --loglevel=info --pool=threads --concurrency=4
```

**Pros:**
- Better concurrency than solo
- Avoids forking issues
- Good for I/O-bound tasks

**Cons:**
- GIL limitations for CPU-bound tasks
- Thread safety concerns

#### Option 3: Use Gevent/Eventlet (Async)
```bash
# Install gevent
pip install gevent

# Run with gevent pool
celery -A core worker --loglevel=info --pool=gevent --concurrency=100
```

**Pros:**
- High concurrency
- Good for I/O-bound tasks
- Avoids forking

**Cons:**
- Requires compatible libraries
- Some Django features may not work

### Quick Fix Script

Use the provided `run_celery.sh` script which auto-detects your platform:

```bash
./run_celery.sh
```

### Production Recommendations

**For Linux Production:**
```bash
celery -A core worker --loglevel=info --pool=prefork --concurrency=8
```

**For macOS Production (if needed):**
```bash
celery -A core worker --loglevel=info --pool=threads --concurrency=4
```

### Configuration

The `core/settings.py` file automatically sets the pool based on platform:
- macOS: `solo` pool
- Linux: `prefork` pool

You can override this by passing `--pool` flag to the worker command.

### Additional Notes

1. **Python 3.14 Compatibility:** Python 3.14 is very new and may have compatibility issues with multiprocessing. Consider using Python 3.11 or 3.12 for production.

2. **Memory Issues:** If workers still crash, check for:
   - Memory leaks in tasks
   - Large object serialization
   - Circular imports

3. **Task Imports:** Ensure all task imports are at the module level, not inside task functions.

### Testing

To verify the fix works:
```bash
# Start worker
celery -A core worker --loglevel=info --pool=solo

# In another terminal, trigger a task
python manage.py shell
>>> from portal.tasks.write_logs_task import write_logs_task
>>> write_logs_task.delay('INFO', 'Test message')
```

If the task completes without SIGSEGV, the fix is working.
