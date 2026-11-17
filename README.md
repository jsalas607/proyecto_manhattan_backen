# Comanda API

Backend for **Comanda**, a multi-tenant restaurant management system ([Flutter app](https://github.com/jsalas607/project_manhattan)).

Async **FastAPI** + **PostgreSQL** + JWT, shipped as two Docker containers and deployed at
`api.manhattan-project.online`.

---

## Why this project is interesting

It's a small SaaS, so the hard part isn't CRUD — it's **making sure nobody sees what they shouldn't**.
Four privilege levels, all enforced in the API (the client only mirrors them):

| Level | Scope |
|---|---|
| **Superadmin** | The platform. Sees everything; creates and deactivates owners (the paying customers). |
| **Owner** (`is_admin`) | A customer. The only one who can create restaurants; sees **only the restaurants they own** (`restaurants.owner_id`). |
| **Manager** | An employee whose role grants `administrar_restaurante`. Manages regular staff, but **cannot see, edit or remove other managers** — nor themselves. |
| **Employee** | Access resolved from their role's permissions **in that specific restaurant**. |

**Tenant isolation:** two owners are invisible to each other. Requesting another owner's restaurant by
id returns `403`, not just a filtered list.

**Deactivation over deletion:** when a customer stops paying, the superadmin flips `is_active`. Their
login is rejected, **existing JWTs stop working immediately** (validated per-request, not just at login),
and their whole tenant freezes — employees included, so nobody keeps using it for free. No data is
deleted: flip it back and everything returns.

## Architecture

```
app/
  core/        config, database, security (JWT + bcrypt), timeutil, permissions catalog
  models/      SQLAlchemy models — 39 tables
  schemas/     Pydantic. camelCase via CamelModel, matching the Dart models 1:1
  api/routers/ 16 routers (auth, restaurants, menu, mesas, pedidos, despacho, ventas, stock,
               inventory, cartera, empleados, admin_users, profile, notifications, uploads, ws)
  ws/          ConnectionManager for WebSocket broadcasts
  deps.py      auth & permission dependencies — where the rules above live
alembic/       migrations
```

**`deps.py` is the heart of it.** Every protected route depends on one of:

- `get_current_user` — decodes the JWT, rejects deactivated accounts.
- `require_superadmin` — platform-only routes.
- `require_restaurant_access` — superadmin, the restaurant's owner, or a member.
- `require_restaurant_owner` — destructive actions (delete/duplicate a restaurant).
- `require_permission("crear_mesa")` — factory that resolves the caller's role **in the restaurant from
  the URL** and checks one of 14 granular permissions. Superadmin and the owner bypass it.

### Data model notes

- **Identity is global, roles are per-restaurant.** A `User` has no role; a `Membership`
  (`user_id` + `restaurant_id` + `role_id`, unique together) grants access to one restaurant with one
  role. The same person can work at two restaurants with different permissions in each.
- **Every tenant-scoped table carries `restaurant_id`** with `ON DELETE CASCADE`, and every query
  filters by it — menu, inventory, sales and cash never leak across restaurants.
- **Timezone matters.** The container runs UTC, the users are in Colombia (UTC-5). A sale at 7pm would
  land on the next UTC day and vanish from "today's sales", so `core/timeutil.py` computes the *local*
  day and its UTC bounds. Used by inventory, sales and cash reports.

## Running it

```bash
cp .env.example .env      # set JWT_SECRET and the admin credentials
docker compose up --build
```

- API: `http://localhost:8000` · Swagger: `/docs` · Health: `/health`
- Migrations run automatically on start (`entrypoint.sh` → `alembic upgrade head`).
- On an empty database a **superadmin** is bootstrapped from `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
  Log in at `POST /api/auth/login` to get the JWT, then create owners from `POST /api/admin/users`.

Send the token as `Authorization: Bearer <jwt>`. Restaurant routes live under `/api/restaurants/{rid}/...`.

## Tests

End-to-end suites that boot the real ASGI app against SQLite — no Docker, no Postgres needed:

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe smoke_test.py       # main flow: restaurant → menu → order → sale → stats
.\.venv\Scripts\python.exe test_isolation.py   # two owners cannot see or touch each other
.\.venv\Scripts\python.exe test_jerarquia.py   # managers can't see/remove other managers
.\.venv\Scripts\python.exe test_superadmin.py  # owner listing, passwords, deactivation & tenant freeze
.\.venv\Scripts\python.exe test_stock.py       # barcodes, stock ledger, sales that deduct stock, reports, Gecofi import
```

Each one asserts the exact status codes (`403` vs `404` vs `409`), because the app relies on them —
a `404` becomes `null`, a `403` becomes a message on screen.

## Migrations

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
```

| Revision | What |
|---|---|
| `0001_initial` | Baseline — creates the schema from the models. |
| `0002_drop_producto_tipo` | Drops an unused product column. |
| `0003_owner_isolation` | `restaurants.owner_id` + `users.is_superadmin`; promotes existing admins to superadmin. |
| `0004_user_is_active` | `users.is_active` for deactivating customers. |
| `0005_stock_retail` | Retail: barcode/cost/stock on `productos`, price and cost frozen on `venta_items`, `stock_movimientos` ledger. |

Migrations use `ADD COLUMN IF NOT EXISTS` so they're idempotent: a fresh database already has the
columns from the baseline's `create_all`, while an existing one gets them applied.

## Retail (liquor stores, convenience stores)

The same restaurant can also sell **packaged products with their own stock**, scanned by barcode.
A product opts in with `controlaStock: true`; dishes keep working exactly as before.

- **Scan:** `GET /restaurants/{rid}/productos/barcode/{code}` (any member, e.g. the cashier) and
  `GET .../productos/buscar?q=` (name contains, or barcode starts with). A USB scanner types the code
  plus Enter, so the client only needs a focused text field.
- **Barcodes are unique per restaurant** (`409` on a duplicate); products without one can coexist.
- **Every stock change goes through the ledger** (`stock_movimientos`, see `services/stock.py`):
  `entrada` (purchase, updates the weighted-average cost), `venta`, `salida` (shrinkage, own use…),
  `ajuste` (physical count) and `importacion`. `PATCH /productos/{id}` never touches stock.
- **Sales freeze `precioUnitario` and `costoUnitario`** on each item and deduct stock in the same
  transaction (`SELECT … FOR UPDATE`). Stock may go negative rather than block a sale of a bottle
  that is physically there; the inventory report counts those products.
- **Reports:** `GET .../reportes/inventario` (value at cost and at sale price, per category) and
  `GET .../reportes/ventas?desde=&hasta=&horaCorte=6` (sales, cost, profit, margin, best sellers and
  stock that left without being sold). `horaCorte` moves the start of the business day for venues
  that close after midnight.
- **Import from Gecofi:** `POST .../import/gecofi` (owner only), idempotent — categories match by
  name, products by barcode or name. `scripts/import_gecofi.py <folder> <rid>` sends the exported
  `categorias.json` + `productos.json`.

| Endpoint | Permission |
|---|---|
| `productos/barcode/{code}`, `productos/buscar` | restaurant access |
| `stock/entradas`, `stock/salidas`, `stock/ajustes`, `stock/movimientos`, `stock/alertas`, `reportes/inventario` | `ver_inventario` |
| `reportes/ventas` | `ver_cartera` |
| `import/gecofi` | owner |

## WebSockets

`ws://<host>/ws/restaurants/{rid}/pedidos?token=<jwt>` and `.../despacho?token=<jwt>` broadcast order
changes per restaurant. The server side is done; the Flutter client currently refreshes over REST, so
this is wired but not yet driving the UI.

## Stack

FastAPI · SQLAlchemy 2 (async) · asyncpg · Alembic · Pydantic v2 · python-jose (JWT) · bcrypt · Docker Compose

---

Built by [jsalas607](https://github.com/jsalas607).
