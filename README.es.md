# TaskFlow API

API REST multi-tenant para la gestión colaborativa de proyectos y tareas, desarrollada con Python, FastAPI y PostgreSQL.

TaskFlow proporciona un espacio de trabajo basado en organizaciones donde los usuarios pueden colaborar en proyectos y gestionar tareas mediante autenticación, control de acceso basado en roles y aislamiento entre organizaciones.

**Idiomas:** [English](README.md) | Español

## Características principales

- **Autenticación JWT:** Registro e inicio de sesión seguros mediante tokens de acceso.
- **Arquitectura multi-tenant:** Los usuarios pueden pertenecer a varias organizaciones.
- **Gestión de organizaciones:** Creación de organizaciones y administración de membresías.
- **Control de acceso basado en roles:** Roles a nivel de organización (OWNER, ADMIN y MEMBER) para la gestión de membresías.
- **Permisos de tareas basados en membresía:** Los miembros activos de una organización pueden crear, actualizar y desactivar tareas.
- **Gestión de proyectos:** Creación y administración de proyectos dentro de las organizaciones.
- **Gestión de tareas:** Organización de tareas y asociación con proyectos.
- **Aislamiento multi-tenant:** Impide el acceso a recursos de organizaciones para las que el usuario no tiene autorización.
- **Integridad referencial:** Las claves foráneas compuestas impiden asociar tareas con proyectos pertenecientes a otras organizaciones.
- **Emails únicos sin distinción de mayúsculas:** Unicidad garantizada directamente por la base de datos.
- **Migraciones de base de datos:** Control y evolución del esquema mediante Alembic.
- **Health checks:** Endpoints para comprobar el estado de la aplicación y la disponibilidad de la base de datos.

## Stack tecnológico

| Categoría               | Tecnología             |
| ----------------------- | ---------------------- |
| Lenguaje                | Python 3.13            |
| Framework API           | FastAPI                |
| Base de datos           | PostgreSQL             |
| ORM                     | SQLAlchemy 2.0 (async) |
| Migraciones             | Alembic                |
| Validación              | Pydantic v2            |
| Autenticación           | JWT, PyJWT             |
| Hash de contraseñas     | Argon2                 |
| Gestión de dependencias | uv                     |
| Contenedores            | Docker, Docker Compose |
| Testing                 | Pytest, pytest-asyncio |
| Testing HTTP            | httpx2                 |
| Calidad de código       | Ruff, Mypy             |

## Arquitectura

La aplicación sigue una arquitectura por capas que separa las responsabilidades HTTP, la lógica de negocio y la persistencia de datos.

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

### Principios arquitectónicos

- **Separación de responsabilidades:** Los endpoints delegan las operaciones de negocio en la capa de servicios.
- **Acceso asíncrono a la base de datos:** SQLAlchemy async y asyncpg.
- **Inyección de dependencias:** FastAPI gestiona las sesiones de base de datos y la autenticación mediante dependencias.
- **Validación de datos:** Los esquemas Pydantic validan las peticiones y respuestas.
- **Integridad de datos:** Las restricciones e índices de base de datos garantizan invariantes importantes.
- **Aislamiento multi-tenant:** Se comprueba la membresía de cada usuario antes de permitir el acceso a recursos de una organización.

## Modelo multi-tenant

TaskFlow utiliza una arquitectura multi-tenant basada en organizaciones.

```text
Usuario
 ├── Organización A (Propietario)
 │    ├── Proyecto 1
 │    │    ├── Tarea 1
 │    │    └── Tarea 2
 │    └── Proyecto 2
 │
 └── Organización B (Miembro)
      └── Proyecto 3
           └── Tarea 3
```

Un usuario puede pertenecer a varias organizaciones y cada organización puede contener múltiples proyectos y tareas.

La membresía determina el acceso a los recursos de cada organización. La autorización se evalúa utilizando el estado actual de la membresía, por lo que eliminar una membresía revoca el acceso incluso si el usuario conserva un JWT emitido anteriormente.

## Instalación y ejecución

### Requisitos

- Docker
- Docker Compose
- Git

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd taskflow-api
```

### 2. Configurar las variables de entorno

```bash
cp .env.example .env
```

Actualiza `.env` con tus propias credenciales y una clave JWT generada de forma segura.

Genera una clave mediante:

```bash
openssl rand -hex 32
```

### 3. Iniciar la aplicación

```bash
docker compose up --build -d
```

La aplicación inicia PostgreSQL y la API. Las migraciones de base de datos se aplican automáticamente mediante el entrypoint del contenedor.

### 4. Comprobar el estado de la aplicación

```bash
curl http://localhost:8000/health
```

Comprobar la disponibilidad de la base de datos:

```bash
curl http://localhost:8000/health/ready
```

### 5. Documentación de la API

Una vez iniciada la aplicación:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Migraciones de base de datos

TaskFlow utiliza Alembic para gestionar los cambios en el esquema de la base de datos.

Las migraciones se aplican automáticamente durante el arranque del contenedor.

Para aplicar las migraciones manualmente en un entorno de desarrollo:

```bash
uv run alembic upgrade head
```

Consultar la migración actual:

```bash
uv run alembic current
```

Comprobar que los modelos SQLAlchemy coinciden con el esquema de la base de datos:

```bash
uv run alembic check
```

## Desarrollo

### Instalar dependencias

```bash
uv sync --group dev
```

### Iniciar el entorno de desarrollo

```bash
docker compose -f compose.yml -f compose.dev.yml up --build
```

La configuración de desarrollo monta el directorio del proyecto y habilita la recarga automática de Uvicorn.

### Ejecutar controles de calidad

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

## Testing

TaskFlow incluye tests unitarios, de API y de integración.

Los tests de integración cubren:

- Persistencia de datos y comportamiento transaccional.
- Aislamiento multi-tenant en operaciones de lectura y escritura.
- Autenticación JWT y revocación de acceso tras eliminar membresías.
- Integridad referencial entre proyectos y tareas.
- Restricciones de base de datos e integridad de los datos.

### Iniciar la base de datos de tests

```bash
docker compose -f compose.test.yml up -d
```

### Configurar la URL de conexión

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://taskflow_test:taskflow_test@127.0.0.1:5433/taskflow_test"
```

### Ejecutar la suite de tests

```bash
uv run pytest
```

### Detener la base de datos de tests

```bash
docker compose -f compose.test.yml down
```

La configuración de los tests de integración valida la conexión a la base de datos para evitar ejecutar accidentalmente los tests contra una base de datos que no sea de pruebas.

## Seguridad y fiabilidad

El proyecto incorpora diferentes medidas de seguridad y fiabilidad:

- Autenticación basada en JWT.
- Hash de contraseñas mediante Argon2.
- Autorización a nivel de organización.
- Aislamiento de acceso entre organizaciones.
- Unicidad de email sin distinción de mayúsculas, garantizada por la base de datos.
- Ejecución de contenedores Docker con un usuario sin privilegios.
- Puertos de API y base de datos publicados únicamente en localhost.
- Health checks de PostgreSQL y comprobaciones de disponibilidad de la API.
- Configuración mediante variables de entorno y placeholders para secretos.
- Operaciones transaccionales y migraciones de base de datos mediante Alembic.

## Decisiones de ingeniería

Algunas decisiones de implementación relevantes para el diseño del proyecto:

- **Unicidad garantizada por la base de datos:** La unicidad del email se implementa mediante un índice único funcional sobre `lower(email)`. Esto evita duplicados independientemente de las mayúsculas y minúsculas, incluso ante operaciones concurrentes.
- **Tests de integración con PostgreSQL real:** Los comportamientos críticos de persistencia y autorización se prueban contra PostgreSQL, en lugar de depender exclusivamente de mocks.
- **Autorización basada en membresías:** El acceso a los recursos de una organización depende de la membresía actual del usuario, no únicamente de la validez del token.
- **Arranque de contenedores con migraciones:** Alembic ejecuta las migraciones antes de iniciar Uvicorn. Existe una variable de entorno que permite desactivar las migraciones automáticas.
- **Contenedores sin privilegios:** La API se ejecuta con un usuario dedicado sin privilegios de administrador.
- **Claves foráneas compuestas:** Las restricciones a nivel de base de datos garantizan la coherencia entre proyectos y organizaciones al asociar tareas.
- **Soft deletion:** Los proyectos y las tareas permiten su desactivación sin eliminar los datos históricos.
- **Testing transaccional:** Los tests de integración utilizan transacciones y savepoints de PostgreSQL para aislar los datos de cada prueba.

## Estado del proyecto

TaskFlow es un proyecto de portfolio en desarrollo activo, centrado en ingeniería backend, diseño de APIs, integridad de bases de datos, autorización multi-tenant y testing automatizado.
