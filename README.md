# Manhattan API

Backend del sistema de gestión de restaurantes **Manhattan** (app Flutter).
FastAPI + PostgreSQL + JWT + WebSockets, desplegable con Docker (2 contenedores).

## Requisitos
- Docker + Docker Compose (recomendado), **o**
- Python 3.12+ y un PostgreSQL local para desarrollo.

## Arranque con Docker (recomendado)
```bash
cp .env.example .env        # ajusta JWT_SECRET y credenciales si quieres
docker compose up --build
```
- API: http://localhost:8000
- Documentación interactiva (Swagger): http://localhost:8000/docs
- Healthcheck: http://localhost:8000/health

Al primer arranque, con la BD vacía, se crea automáticamente el **admin global**
usando `ADMIN_USERNAME` / `ADMIN_PASSWORD` del `.env`. Inicia sesión en
`POST /api/auth/login` para obtener el JWT.

## Estructura
```
app/
  core/        config, database, security (JWT+bcrypt), permissions
  models/      modelos SQLAlchemy (31 tablas)
  schemas/     Pydantic en camelCase (CamelModel) — coincide con los modelos Dart
  api/routers/ un router por módulo (auth, restaurants, menu, mesas, pedidos, ...)
  ws/          ConnectionManager para WebSockets
  deps.py      dependencias de auth/permisos
alembic/       migraciones (baseline 0001_initial)
```

## Autenticación
- `POST /api/auth/login` → `{ access_token, user }`. Enviar `Authorization: Bearer <token>`.
- Usuarios pueden pertenecer a varios restaurantes con rol distinto (tabla `memberships`).
- Rutas por sucursal: `/api/restaurants/{rid}/...`. Permisos resueltos por el rol del
  usuario en ese restaurante; el admin global accede a todo.

## WebSockets (tiempo real)
- Pedidos en vivo: `ws://localhost:8000/ws/restaurants/{rid}/pedidos?token=<jwt>`
- Pantallas de despacho: `ws://localhost:8000/ws/restaurants/{rid}/despacho?token=<jwt>`

## Desarrollo / prueba sin Docker
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# prueba de humo end-to-end contra SQLite (no necesita Postgres):
$env:PYTHONWARNINGS="ignore"; .\.venv\Scripts\python.exe smoke_test.py
```

## Migraciones
- Baseline `alembic/versions/0001_initial.py` crea el esquema (`alembic upgrade head`,
  se ejecuta solo en el `entrypoint.sh` al arrancar el contenedor).
- Nuevas migraciones: `alembic revision --autogenerate -m "mensaje"`.
