# Cleanup Features - Summary of Changes

## Overview
Added automatic cleanup features for session-specific and temporary folders in the CLI version of the RAG chatbot.

## Features Added

### 1. Automatic Cleanup of Temporary Folders on Exit
- **What**: Automatically deletes all `vector_store_tmp_*` folders when the user exits the CLI
- **When**: Triggered when user types `exit`, `quit`, or presses Ctrl+C
- **Why**: These temporary folders are created when the main vector store is locked, and they can accumulate over time

### 2. Session Cleanup Prompt on Startup
- **What**: Interactive prompt asking users if they want to delete session-specific data before processing
- **Folders affected**:
  - `local_store/` - Contains processed markdown and metadata from PDFs
  - `vector_store/` - Contains the vector database
- **Options**:
  - Answer `y` to delete and start fresh
  - Answer `n` to keep existing data
  - Use `--no-cleanup-prompt` flag to skip the prompt entirely

## Code Changes

### src/cli_run.py

#### New Functions Added:

1. **`cleanup_temp_folders()`**
   - Finds all `vector_store_tmp_*` folders in the project root
   - Deletes them using `shutil.rmtree()`
   - Logs the cleanup operation

2. **`cleanup_session_folders()`**
   - Deletes `local_store/` and `vector_store/` directories
   - Provides user feedback on success/failure

3. **`prompt_cleanup_session()`**
   - Interactive prompt for users
   - Returns boolean indicating user's choice

#### Modified Functions:

1. **`run_repl(retriever)`**
   - Added `cleanup_temp_folders()` call on exit (both normal and interrupt)

2. **`main()`**
   - Added `--no-cleanup-prompt` argument
   - Added call to `prompt_cleanup_session()` unless flag is set

#### New Import:
- Added `import glob` to find temporary folders using pattern matching

### README.md

Added comprehensive documentation:
- New "Session Cleanup Options" section
- Usage examples with different flags
- Updated troubleshooting notes

## Usage Examples

### Basic usage (with cleanup prompt):
```bash
python src/cli_run.py --pdf main.pdf
```

### Skip cleanup prompt:
```bash
python src/cli_run.py --pdf main.pdf --no-cleanup-prompt
```

### Force reindex with cleanup:
```bash
python src/cli_run.py --pdf main.pdf --force
```

## Testing

Tested successfully:
- ✓ Cleanup of 6 temporary folders
- ✓ Functions work correctly with project_root path
- ✓ Graceful handling of non-existent folders
- ✓ Proper logging of all operations

## Benefits

1. **Disk Space Management**: Automatically cleans up temporary files that can accumulate
2. **Fresh Start Option**: Easy way to start with a clean slate for new documents
3. **User Control**: Interactive prompt gives users control over cleanup decisions
4. **Flexibility**: Command-line flag for automation/scripting scenarios
