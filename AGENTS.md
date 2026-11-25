# AGENTS.md

# TaskFlow API

## 1. Project Overview

TaskFlow API is a multi-tenant REST API for collaborative project and task management.

The application allows users to:

- Register and authenticate using JWT.
- Create and manage organizations.
- Add existing users as organization members.
- Manage organization memberships and roles (OWNER, ADMIN and MEMBER).
- Create and manage projects within organizations.
- Create, assign, update and deactivate tasks.
- Access organization-scoped resources according to their current membership.
- Maintain tenant isolation through application-level authorization and database constraints.

The goal is to build a maintainable, secure and well-tested backend using modern Python technologies.

## 2. Technology Stack

Use the existing project dependencies and architecture. Do not introduce alternative technologies without explicit justification.

- Python 3.13
- FastAPI
- Uvicorn
- SQLAlchemy 2.x (async)
- PostgreSQL
- asyncpg
- Pydantic v2
- Alembic
- Docker and Docker Compose
- uv
- Pytest and pytest-asyncio
- Ruff
- Mypy

## 3. Project Architecture

The application follows a layered architecture:

- `app/api/`: HTTP endpoints and API routing.
- `app/core/`: Configuration, authentication, security and database infrastructure.
- `app/models/`: SQLAlchemy ORM models.
- `app/schemas/`: Pydantic request and response schemas.
- `app/services/`: Business logic and database operations.
- `migrations/`: Alembic database migrations.
- `tests/`: Unit, API, integration, infrastructure and schema tests.

### Architecture rules

- Keep HTTP handling in API endpoints.
- Keep business logic in service modules.
- Use Pydantic schemas for request validation and response serialization.
- Use SQLAlchemy async APIs for database operations.
- Use FastAPI dependency injection for database sessions and authentication.
- Avoid duplicating business logic across endpoints.

## 4. Python Coding Standards

- Use Python 3.13 features where appropriate.
- Add type annotations to functions, methods and public interfaces.
- Prefer explicit types over `Any`.
- Use async functions for asynchronous database operations.
- Follow existing naming conventions and module organization.
- Keep functions focused and avoid unnecessary abstractions.
- Use Ruff for linting and formatting.
- Ensure changes pass Mypy.

Do not introduce new dependencies when existing project dependencies provide the required functionality.

## 5. Database and SQLAlchemy Rules

- Use SQLAlchemy 2.x declarative mappings.
- Use `AsyncSession` for database operations.
- Keep database access inside the service layer or existing infrastructure abstractions.
- Use explicit transaction handling and preserve the existing session lifecycle.
- Define database constraints and indexes for important data invariants.
- Use Alembic for all database schema changes.
- Never modify an existing migration that may already have been applied. Create a new migration instead.

### Data integrity

- Organization memberships are unique per organization and user.
- User email uniqueness is case-insensitive and enforced by a functional unique index on `lower(email)`.
- Project slugs are unique within their organization.
- Tasks must reference projects belonging to the same organization.
- The task-project relationship is protected by a composite foreign key.

Do not weaken database constraints to make application code or tests pass.

## 6. Multi-Tenant Authorization

Tenant isolation is a core security requirement.

- Verify current organization membership before accessing organization-scoped resources.
- Never trust an organization ID, project ID or task ID supplied by the client without validating access.
- Apply authorization using the current database membership state, not only JWT claims.
- Removing an organization membership must revoke access immediately, even if the user still has a valid JWT.
- Prevent cross-organization access to projects and tasks.
- Preserve existing HTTP error semantics, including 404 responses for inaccessible resources where implemented.

### Organization roles

The supported organization roles are:

- `OWNER`
- `ADMIN`
- `MEMBER`

Follow the existing role-based authorization rules for organization membership management.

### Task permissions

Any active organization member can create, update and deactivate tasks.

Do not introduce role-based restrictions for task write operations unless explicitly approved.

## 7. Authentication and Security

- Use the existing JWT authentication implementation.
- Use Argon2 password hashing through the current password hashing library.
- Never store or log plaintext passwords.
- Never expose password hashes or sensitive authentication data in API responses.
- Preserve existing token validation and inactive-user behavior.
- Do not weaken authentication or authorization checks.
- Read secrets and environment-specific configuration through the existing settings system.
- Never commit real credentials, secrets or production environment files.

## 8. Testing Requirements

Every meaningful behavior change must include appropriate tests.

Use the existing test organization:

- `tests/api/`: API endpoint tests.
- `tests/integration/`: PostgreSQL integration tests.
- `tests/infrastructure/`: Infrastructure and configuration tests.
- `tests/schemas/`: Pydantic schema tests.
- `tests/services/`: Business logic tests.

### Testing rules

- Use mocks for isolated unit tests where appropriate.
- Use real PostgreSQL integration tests for persistence, database constraints and tenant isolation.
- Test both successful operations and relevant failure cases.
- Verify that unauthorized cross-tenant operations do not modify data.
- Preserve test database safety checks.
- Do not replace integration tests with mocks when database behavior is what needs validation.

## 9. Required Validation

Before considering a change complete, run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

If a change affects database models or migrations, also verify:

```bash
uv run alembic check
```

For migration changes, verify that the migration can be applied successfully against the dedicated test database.

Do not claim that checks pass unless they have actually been executed.

## 10. Development Workflow

Before modifying code:

1. Inspect the relevant implementation and existing tests.
2. Understand the current architecture and conventions.
3. Identify potential impacts on database integrity, authorization and tenant isolation.
4. Prefer minimal changes that solve the actual requirement.

When implementing changes:

- Preserve existing public API behavior unless a change is explicitly requested.
- Update or add tests alongside implementation changes.
- Avoid unrelated refactoring.
- Do not introduce new abstractions without a clear benefit.
- Update documentation when implementation or configuration changes affect it.

## 11. Important Project Decisions

The following are established project decisions and must not be changed implicitly:

- Organization memberships are physically deleted when removed.
- Task write operations are available to all active organization members, regardless of role.
- Project deactivation does not automatically deactivate or delete its tasks.
- Project and task deactivation preserve historical records.
- Username uniqueness is case-sensitive.
- Email uniqueness is case-insensitive.
- Task-project organization consistency is enforced through a composite foreign key.
- Access and refresh token separation does not currently rely on an additional JWT `type` claim.

If a requirement conflicts with these decisions, explain the conflict and request clarification before changing the behavior.

## 12. Scope and Dependencies

- Do not add features that have not been requested.
- Do not change dependencies or introduce new libraries without justification.
- Do not modify Docker, Compose or environment configuration unnecessarily.
- Do not make destructive database changes without explicit approval.
- Do not weaken security, validation or database integrity to simplify implementation.
