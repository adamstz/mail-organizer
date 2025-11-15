# Storage Schema Documentation

This document describes the consistent schema across all storage backends (PostgreSQL, SQLite, and InMemory).

## Schema Version

Last updated: 2025-11-15
Schema version: 2.0 (after migration 002)

## Core Tables

### messages

Stores email message data from Gmail.

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| id | TEXT/STRING | Primary key, Gmail message ID | Required |
| thread_id | TEXT/STRING | Gmail thread ID | Optional |
| from_addr | TEXT/STRING | Sender email address | Optional |
| to_addr | TEXT/STRING | Recipient email address | Optional |
| subject | TEXT/STRING | Email subject line | Optional |
| snippet | TEXT/STRING | Email snippet/preview | Optional |
| labels | JSON/JSONB | Gmail labels (array) | Serialized as JSON |
| internal_date | BIGINT/INTEGER | Gmail internal date timestamp | Milliseconds since epoch |
| payload | JSON/JSONB | Full message payload | Serialized as JSON, large |
| raw | TEXT/STRING | Raw message content | Optional, base64 encoded |
| headers | JSON/JSONB | Email headers (dict) | Serialized as JSON |
| fetched_at | TIMESTAMP/TEXT | When message was fetched | Auto-set on save |
| has_attachments | BOOLEAN/INTEGER | Whether message has attachments | Default: FALSE/0 |
| latest_classification_id | TEXT/STRING | FK to classifications.id | Optional, indicates latest classification |

**Foreign Keys:**
- `latest_classification_id` → `classifications.id`

**Deprecated Columns (SQLite only for backward compatibility):**
- `classification_labels` - No longer written to, use JOIN with classifications table
- `priority` - No longer written to, use JOIN with classifications table  
- `summary` - No longer written to, use JOIN with classifications table

### classifications

Stores classification results from LLM processing. Multiple classifications can exist per message (history).

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| id | TEXT/STRING | Primary key, UUID | Required |
| message_id | TEXT/STRING | FK to messages.id | Required |
| labels | JSON/JSONB | Classification labels (array) | Serialized as JSON |
| priority | TEXT/STRING | Priority level (High/Medium/Low) | Optional |
| summary | TEXT/STRING | Classification summary | Optional |
| model | TEXT/STRING | Model used for classification | Optional |
| created_at | TIMESTAMP/TEXT | When classification was created | Required, ISO 8601 format |

**Foreign Keys:**
- `message_id` → `messages.id`

### metadata

Stores key-value configuration and state.

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| key | TEXT/STRING | Primary key | Required |
| value | TEXT/STRING | Value for the key | Required |

**Common keys:**
- `historyId` - Gmail sync history ID for incremental updates

## Indexes

### PostgreSQL Indexes

For performance, PostgreSQL has the following indexes:

**On classifications:**
- `idx_classifications_message_id` - ON classifications(message_id)
- `idx_classifications_created_at` - ON classifications(created_at DESC)
- `idx_classifications_labels_gin` - GIN index on labels JSONB for fast label filtering
- `idx_classifications_priority` - ON classifications(priority) WHERE priority IS NOT NULL

**On messages:**
- `idx_messages_fetched_at` - ON messages(fetched_at DESC)
- `idx_messages_latest_classification` - ON messages(latest_classification_id) WHERE NOT NULL

### SQLite Indexes

SQLite has basic indexes:
- `idx_classifications_message_id` - ON classifications(message_id)
- `idx_classifications_created_at` - ON classifications(created_at DESC)

## Storage Interface Methods

All storage backends must implement these methods (see `storage_interface.py`):

### Basic Operations
- `init_db()` - Initialize schema
- `save_message(msg: MailMessage)` - Save/update a message
- `get_message_ids() -> List[str]` - Get all message IDs
- `get_message_by_id(message_id: str) -> Optional[MailMessage]` - Get single message
- `list_messages(limit: int, offset: int) -> List[MailMessage]` - List messages with pagination

### Classification Operations
- `create_classification(message_id, labels, priority, summary, model) -> str` - Create new classification and link to message
- `get_latest_classification(message_id: str) -> Optional[dict]` - Get latest classification for a message
- `save_classification_record(record)` - Save a ClassificationRecord object
- `list_classification_records_for_message(message_id: str)` - Get all classifications for a message (history)
- `get_unclassified_message_ids() -> List[str]` - Get IDs of unclassified messages
- `count_classified_messages() -> int` - Count classified messages

### Filtering Operations (Added in v2.0)
- `list_messages_by_label(label: str, limit: int, offset: int) -> tuple[List[MailMessage], int]` - Filter by label
- `list_messages_by_priority(priority: str, limit: int, offset: int) -> tuple[List[MailMessage], int]` - Filter by priority
- `list_classified_messages(limit: int, offset: int) -> tuple[List[MailMessage], int]` - Only classified messages
- `list_unclassified_messages(limit: int, offset: int) -> tuple[List[MailMessage], int]` - Only unclassified messages
- `get_label_counts() -> dict` - Get all labels with counts

### Metadata Operations
- `get_history_id() -> Optional[str]` - Get Gmail history ID
- `set_history_id(history_id: str)` - Set Gmail history ID

## Data Models

### MailMessage

See `src/models/message.py` for the full dataclass definition.

Key fields:
- Core message data (id, subject, from, to, etc.)
- `has_attachments: bool` - Detected from payload
- Classification fields (populated from JOIN with classifications table):
  - `classification_labels: Optional[List[str]]`
  - `priority: Optional[str]`
  - `summary: Optional[str]`

### ClassificationRecord

See `src/models/classification_record.py` for the full dataclass definition.

Key fields:
- `id: str` - UUID
- `message_id: str` - Reference to message
- `labels: List[str]` - Classification labels
- `priority: Optional[str]` - Priority level
- `summary: Optional[str]` - Summary text
- `model: Optional[str]` - Model used
- `created_at: Optional[datetime]` - Creation timestamp

## Migration History

### Migration 001 (Initial)
- Added `latest_classification_id` to messages table
- Moved classification data from messages to classifications table
- Added foreign key constraints

### Migration 002 (Performance)
- Added GIN index on classifications.labels (PostgreSQL only)
- Added index on classifications.priority (PostgreSQL only)
- Added index on messages.latest_classification_id (PostgreSQL only)
- Performance improvements: 10-100x faster tag/priority filtering

## Backend-Specific Notes

### PostgreSQL
- Uses JSONB for JSON columns (more efficient than JSON)
- Uses GIN indexes for fast JSONB queries
- Best for production use with large datasets

### SQLite
- Uses TEXT for JSON columns with JSON serialization
- Row factory set to `sqlite3.Row` for named column access
- Deprecated columns kept for backward compatibility during migration
- Best for development and small deployments

### InMemory
- Uses Python dictionaries
- No persistence (data lost on process exit)
- Best for testing only

## Query Patterns

### Getting a message with its latest classification

```python
# All backends do this automatically in get_message_by_id()
message = storage.get_message_by_id(message_id)
# message.classification_labels, message.priority, message.summary are populated
```

### Creating a classification

```python
# This creates the classification record AND links it to the message
classification_id = storage.create_classification(
    message_id="msg123",
    labels=["Work", "Action Required"],
    priority="High",
    summary="Project update email",
    model="gpt-4"
)
```

### Filtering messages by label (fast)

```python
# PostgreSQL uses GIN index, SQLite uses LIKE with post-filter
messages, total = storage.list_messages_by_label("Work", limit=50, offset=0)
```

### Getting label statistics

```python
# PostgreSQL uses native JSONB query, SQLite/InMemory counts in Python
label_counts = storage.get_label_counts()  # {"Work": 150, "Personal": 75, ...}
```

## Important Notes

1. **Never write classification data directly to messages table** - Always use `create_classification()` or `save_classification_record()`

2. **Use JOINs to get classification data** - All `list_messages*` and `get_message_by_id` methods automatically JOIN with classifications table

3. **Pagination consistency** - Filtering methods return `(messages, total_count)` tuple for consistent pagination

4. **Column access in SQLite** - Always use named column access (`row['column_name']`) instead of positional indices to avoid fragility

5. **JSONB vs JSON** - PostgreSQL uses JSONB (binary JSON) for better performance, SQLite uses TEXT with JSON serialization
