"""Importa a un restaurante los datos exportados de Gecofi, vía la API.

Lee `categorias.json` y `productos.json` de una carpeta (el formato que deja la
exportación de Gecofi) y los manda a `POST /api/restaurants/{rid}/import/gecofi`.
Se puede repetir sin duplicar productos.

Uso:

    python scripts/import_gecofi.py <carpeta> <restaurant_id> \\
        [--api https://api.manhattan-project.online] [--actualizar-stock]

Pide usuario y contraseña del DUEÑO del restaurante (o lee MANHATTAN_USER /
MANHATTAN_PASSWORD). Solo usa la librería estándar.
"""

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _post(url: str, body: dict, token: str | None = None) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Error {e.code} en {url}: {e.read().decode(errors='replace')}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("restaurant_id")
    ap.add_argument("--api", default="https://api.manhattan-project.online")
    ap.add_argument("--actualizar-stock", action="store_true",
                    help="en productos ya existentes, iguala el stock al del archivo")
    args = ap.parse_args()

    categorias = json.loads((args.carpeta / "categorias.json").read_text(encoding="utf-8"))
    productos = json.loads((args.carpeta / "productos.json").read_text(encoding="utf-8"))
    print(f"{len(categorias)} categorías y {len(productos)} productos en {args.carpeta}")

    user = os.environ.get("MANHATTAN_USER") or input("Usuario dueño: ")
    password = os.environ.get("MANHATTAN_PASSWORD") or getpass.getpass("Contraseña: ")
    api = args.api.rstrip("/") + "/api"
    token = _post(f"{api}/auth/login", {"username": user, "password": password})["access_token"]

    res = _post(
        f"{api}/restaurants/{args.restaurant_id}/import/gecofi",
        {"categorias": categorias, "productos": productos,
         "actualizarStock": args.actualizar_stock},
        token,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
