# Contributing to ztrader

## Language and Coding Standards
- **Communication**: Always talk in Thai when interacting with users.
- **Code & Technical Assets**: All code, comments, documentation, and technical definitions must be in English.

Thank you for your interest in contributing to **ztrader**! This is a safety-first, multi-language algorithmic trading platform. To maintain our high standards of safety, quality, and maintainability, please follow these guidelines.

---

## 1. Development Environment Setup

### Backend (FastAPI + SQLAlchemy + PostgreSQL)
1. Navigate to the backend directory:
   ```bash
   cd backend/
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies in editable mode:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -e .
   ```
4. Copy the `.env.example` file and set up variables:
   ```bash
   cp .env.example .env
   ```
   *Note: Never commit your local `.env` file.*

### Frontend (Next.js)
1. Navigate to the frontend directory:
   ```bash
   cd frontend/
   ```
2. Install dependencies:
   ```bash
   npm install # or pnpm install / yarn
   ```

---

## 2. Coding Standards & Conventions

- **Safety-First Code**:
  - Do not hardcode API keys, tokens, passwords, or secrets. Use environment variables.
  - Implement all trading intents to pass through the fail-closed `RiskEngine`.
  - Always default `EXECUTION_MODE` to `paper`.
- **SQL Security**:
  - Always write parameterized queries or use SQLAlchemy ORM expressions. Never use string formatting for SQL parameters.
- **Python Quality**:
  - Format with Ruff/Black.
  - No trailing whitespaces at the end of files or lines.
- **TypeScript & CSS**:
  - Use Next.js App Router.
  - Localize all user-facing copy using `react-i18next` namespaces.

---

## 3. Testing & TDD (Test-Driven Development)

- We follow a strict test-driven development workflow:
  1. Write tests that fail first.
  2. Implement the minimal code needed to pass the tests.
  3. Refactor.
- Run the test suite:
  ```bash
  PYTHONPATH=src pytest tests/
  ```
- All new features or bug fixes must include unit or integration tests with **80%+ coverage**.

---

## 4. Git & Commit Message Workflow

We use **Conventional Commits**:
- `feat(ztrader): <description>` for new features
- `fix(ztrader): <description>` for bug fixes
- `docs(ztrader): <description>` for documentation updates
- `test(ztrader): <description>` for test additions
- `chore(ztrader): <description>` for dependency or configuration updates

Before pushing, ensure:
- All tests pass: `make test` or `pytest`
- No trailing whitespaces: `git diff --check`
- No secrets staged
