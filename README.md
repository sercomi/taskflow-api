# TaskFlow API

A multi-tenant REST API for collaborative project and task management, built with Python, FastAPI and PostgreSQL.

TaskFlow provides an organization-based workspace where users can collaborate on projects and manage tasks with authentication, role-based access control and tenant isolation.

**Languages:** English | [Español](README.es.md)

## Features

- **JWT Authentication:** Secure user registration and login using access tokens.
- **Multi-tenant architecture:** Users can belong to multiple organizations.
- **Organization management:** Create organizations and manage memberships.
- **Role-based access control:** Organization-level roles, including owners and members.
- **Project management:** Create and manage projects within organizations.
- **Task management:** Organize tasks and associate them with projects.
- **Tenant isolation:** Prevent users from accessing resources belonging to organizations they are not authorized to access.
- **Case-insensitive email uniqueness:** Database-enforced uniqueness regardless of email casing.
- **Database migrations:** Schema versioning and management with Alembic.
- **Health checks:** Application and database readiness endpoints.

## Tech Stack

| Category           | Technology             |
| ------------------ | ---------------------- |
| Language           | Python 3.13            |
| API Framework      | FastAPI                |
| Database           | PostgreSQL             |
| ORM                | SQLAlchemy 2.0 (async) |
| Migrations         | Alembic                |
| Validation         | Pydantic v2            |
| Authentication     | JWT, PyJWT             |
| Password Hashing   | Argon2                 |
| Package Management | uv                     |
| Containerization   | Docker, Docker Compose |
| Testing            | Pytest, pytest-asyncio |
| HTTP Testing       | httpx2                 |
| Code Quality       | Ruff, Mypy             |

## Architecture

The application follows a layered architecture that separates HTTP concerns, business logic and data persistence.

```text
app/
├── api/
│   └── v1/
│       └── endpoints/
├── core/
│   ├── auth.py
│   ├── base.py
│   ├── config.py
│   ├── database.py
│   └── security.py
├── models/
├── schemas/
└── services/

migrations/
tests/
├── api/
├── integration/
├── infrastructure/
├── schemas/
└── services/
```

### Architectural principles

- **Separation of concerns:** API endpoints delegate business operations to service layers.
- **Asynchronous database access:** SQLAlchemy async and asyncpg.
- **Dependency injection:** FastAPI dependencies manage database sessions and authentication.
- **Data validation:** Pydantic schemas validate incoming requests and outgoing responses.
- **Database integrity:** Constraints and indexes enforce important data invariants.
- **Tenant isolation:** Organization membership is checked before accessing organization-scoped resources.

## Multi-Tenant Model

TaskFlow uses an organization-based multi-tenant architecture.

```text
User
 ├── Organization A (Owner)
 │    ├── Project 1
 │    │    ├── Task 1
 │    │    └── Task 2
 │    └── Project 2
 │
 └── Organization B (Member)
      └── Project 3
           └── Task 3
```

A user can belong to multiple organizations, and each organization can contain multiple projects and tasks.

Organization membership determines access to organization-scoped resources. Authorization is evaluated against the current membership state, so removing a membership revokes access even when the user still holds a previously issued JWT.

## Getting Started

### Requirements

- Docker
- Docker Compose
- Git

### 1. Clone the repository

```bash
git clone <repository-url>
cd taskflow-api
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Update `.env` with your own credentials and a securely generated JWT secret.

Generate a secret with:

```bash
openssl rand -hex 32
```

### 3. Start the application

```bash
docker compose up --build -d
```

The application starts PostgreSQL and the API. Database migrations are automatically applied by the container entrypoint.

### 4. Check application health

```bash
curl http://localhost:8000/health
```

Check database readiness:

```bash
curl http://localhost:8000/health/ready
```

### 5. API documentation

Once the application is running:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database Migrations

TaskFlow uses Alembic to manage database schema changes.

Migrations are automatically applied during container startup.

To apply migrations manually in a development environment:

```bash
uv run alembic upgrade head
```

To check the current migration:

```bash
uv run alembic current
```

To verify that SQLAlchemy models match the database schema:

```bash
uv run alembic check
```

## Development

### Install dependencies

```bash
uv sync --group dev
```

### Start the development environment

```bash
docker compose -f compose.yml -f compose.dev.yml up --build
```

The development configuration mounts the project directory and enables Uvicorn reload.

### Run code quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

## Testing

TaskFlow includes unit, API and integration tests.

Integration tests use a dedicated PostgreSQL database to validate real database behavior, persistence and tenant isolation.

Start the test database:

```bash
docker compose -f compose.test.yml up -d
```

Configure the test database URL:

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://taskflow_test:taskflow_test@127.0.0.1:5433/taskflow_test"
```

Run the test suite:

```bash
uv run pytest
```

Stop the test database:

```bash
docker compose -f compose.test.yml down
```

The integration test configuration validates the database connection to prevent accidentally running tests against a non-test database.

## Security and Reliability

The project incorporates several security and reliability measures:

- JWT-based authentication.
- Argon2 password hashing.
- Organization-level authorization.
- Multi-tenant access isolation.
- Database-enforced case-insensitive email uniqueness.
- Non-root Docker runtime user.
- Localhost-only published database and API ports.
- PostgreSQL health checks and API readiness checks.
- Environment-based configuration and secret placeholders.
- Transactional database operations and Alembic migrations.

## Engineering Decisions

Some implementation decisions are particularly relevant to the project's design:

- **Database-enforced uniqueness:** Email uniqueness is implemented using a functional unique index on `lower(email)`, preventing case-sensitive duplicates even under concurrent requests.
- **Real PostgreSQL integration tests:** Critical persistence and authorization behavior is tested against PostgreSQL instead of relying exclusively on mocks.
- **Membership-based authorization:** Access to organization resources depends on current membership, not only on token validity.
- **Migration-aware container startup:** Alembic migrations run before Uvicorn starts, with an environment variable available to disable automatic migrations.
- **Non-root containers:** The API runs under a dedicated unprivileged user.

## Project Status

TaskFlow is an actively developed portfolio project focused on backend engineering, API design, database integrity, multi-tenant authorization and automated testing.
