# Primed - Backend

FastAPI-based backend for the Primed app.

The front-end app code can be found [here](https://github.com/Dhairya10/primed-app)

## Tech Stack

- **FastAPI** - Web API framework
- **Supabase** - PostgreSQL database and authentication
- **Pydantic v2** - Data validation
- **UV** - Package manager
- **Pytest** - Testing framework
- **Ruff** - Linting and formatting
- **Opik** - Agent Tracking and Evaluation

## Prerequisites

- Python 3.12+
- UV package manager ([installation guide](https://github.com/astral-sh/uv))
- Supabase account and project

## Quick Start

### 1. Install UV (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and Setup

```bash
cd primed-api
uv venv
uv sync
```

### 3. Run the Application

**Option 1: Quick Start Script**
```bash
bash run.sh
```

**Option 2: Manual Start**
```bash
uv run uvicorn src.prep.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### 4. Access API Documentation

Once running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Testing

### Run all tests
```bash
uv run pytest
```

### Run with coverage
```bash
uv run pytest --cov=src --cov-report=term-missing -v
```

### Run specific test file
```bash
uv run pytest src/prep/features/[feature_name]/tests/test_handlers.py -v
```

## Code Quality

### Format code
```bash
uv run ruff format .
```

### Check linting
```bash
uv run ruff check .
```

### Auto-fix linting issues
```bash
uv run ruff check --fix .
```

### Type checking
```bash
uv run mypy src/
```

