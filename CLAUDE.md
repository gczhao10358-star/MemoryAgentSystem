# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

智忆助理 (MemoryMate) is a personalized long-term memory agent system. It provides a conversational AI with multi-level memory storage (working, short-term, long-term), hybrid retrieval (dense + sparse + RRF fusion), user profile learning, and task scheduling with Lark (飞书) integration.

## Development Commands

### Environment Setup

The project uses a Python virtual environment at `.venv`:

**Windows:**
```bash
uv venv
.venv\Scripts\pip.exe install -r requirements.txt
```

**macOS/Linux:**
```bash
uv venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Application

**Full Web Service (Backend + Frontend):**
```bash
# Windows
start_server.bat

# Or manually - Backend
source .venv/bin/activate && python api.py

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

**Frontend Build:**
```bash
cd frontend
npm install
npm run build
```

Built files are served from `frontend/dist/` via FastAPI static files.

**Command-line interactive mode:**
```bash
source .venv/bin/activate && python main.py
```

**Demo mode:**
```bash
source .venv/bin/activate && python main.py --demo
```

### Testing

Tests are standalone async scripts (not using pytest):

```bash
# Run all tests individually
source .venv/bin/activate && python tests/test_basic.py
source .venv/bin/activate && python tests/test_system.py
source .venv/bin/activate && python tests/test_api.py
source .venv/bin/activate && python tests/test_time_parser.py
```

## Architecture

### Core Agent

**MemoryMateAgent** (`memory_assistant/core/memory_mate_agent.py`) is the main orchestrator that initializes and coordinates all subsystems:
- `MemoryStorage`: Unified interface combining FAISS vector store + SQLite metadata store
- `MemoryManager`: Handles working memory (conversation turns) and short-term memory
- `HybridRetrievalEngine`: Dense retrieval (FAISS) + sparse retrieval (BM25) + RRF fusion + personalization reranking
- `ProfileManager` / `ProfileLearner`: User profile storage and preference learning
- `MemoryEvolutionEngine`: Time-based decay and reinforcement of memories
- `MemoryWorkflowEngine`: Intent classification (CHAT, STORE, RETRIEVE, EXECUTE_TASK) and workflow routing
- `PreciseScheduler`: Asyncio-based task scheduling with persistence

### Chat Data Flow

1. User message → `IntentType` classification
2. Hybrid search retrieves relevant memories (dense + sparse → RRF → personalized rerank)
3. User profile loaded and incorporated into context
4. LLM generates response with memory context
5. New memories extracted and stored (subject to content filtering)
6. Profile learner updates user preferences

### Storage System

**Dual Storage:**
- `FaissVectorStore`: FAISS index for vector similarity search (path: `./data/vector_index/`)
- `SQLiteMetadataStore`: SQLite for metadata, tags, and relationships (path: `./data/memory.db`)
- `MemoryStorage` unifies both with transactional semantics

### Memory Tiers

- **Working Memory**: Recent conversation turns (max 20 turns), ephemeral
- **Short-term Memory**: Recent facts with TTL (max 100 entries, 7-day TTL)
- **Long-term Memory**: Persistent facts with evolution tracking (stored in FAISS + SQLite)

### Task Scheduling

**PreciseScheduler** (`memory_assistant/core/precise_scheduler.py`):
- Asyncio-based millisecond-precision scheduler
- Tasks persisted to SQLite, survive restarts
- Integrates with Lark (飞书) for external notifications
- WebSocket for real-time push to frontend

### Document Processing

**DocumentProcessor** (`memory_assistant/ingestion/document_processor.py`):
- ETL pipeline for meeting document parsing
- Supports PDF, DOCX, TXT, Markdown formats
- Two-stage LLM analysis (global + chunk-based)
- WebSocket real-time progress streaming

### Platform Integration

**Lark Adapter** (`memory_assistant/platform/lark_adapter.py`):
- Configurable per-user via API/frontend
- Sends reminder notifications to Lark
- Requires `app_id`, `app_secret`, `receive_id`

## Configuration

Key config in `config.yaml`:

```yaml
llm:
  api_key: "..."
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model: "qwen3.5-flash"

embedding:
  model: "text-embedding-v3"
  dimension: 1024

storage:
  data_dir: "./data"
```

## API Endpoints

FastAPI service (`api.py`) exposes:

- `POST /api/chat` - Main chat endpoint
- `POST /api/remember` - Explicit memory storage
- `POST /api/search` - Memory search
- `POST /api/tasks` - Create scheduled task/reminder
- `POST /api/documents/upload` - Upload meeting documents
- `WS /ws/documents/{document_id}` - Document processing progress
- `WS /ws/{user_id}` - WebSocket for real-time reminders
- `/api/platform/lark/*` - Lark platform configuration

API docs at `http://localhost:8000/docs`

## Key File Locations

- `config.yaml` - Main configuration (LLM keys, paths, thresholds)
- `data/memory.db` - SQLite metadata database
- `data/vector_index/` - FAISS vector index files
- `frontend/dist/` - Built frontend assets (served by FastAPI)
- `logs/` - Application logs
