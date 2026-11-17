from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.deps import require_permission, require_restaurant_access
from app.models.menu import (
    Categoria,
    IngredienteOpcion,
    Producto,
    ProductoIngrediente,
)
from app.models.organization import User
from app.schemas.menu import (
    CategoriaCreate,
    CategoriaOut,
    IngredienteRecetaOut,
    OpcionRecetaOut,
    ProductoCreate,
    ProductoOut,
    ProductoUpdate,
)
from app.services.stock import asegurar_codigo_libre, mover_stock, normalizar_codigo

router = APIRouter(prefix="/restaurants/{rid}", tags=["menu"])


# ----------------- Categorías -----------------
@router.get("/categorias", response_model=list[CategoriaOut])
async def list_categorias(
    rid: str, _: User = Depends(require_restaurant_access), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Categoria).where(Categoria.restaurant_id == rid))
    return [CategoriaOut.model_validate(c) for c in result.scalars().all()]


@router.post("/categorias", response_model=CategoriaOut, status_code=201)
async def add_categoria(
    rid: str,
    body: CategoriaCreate,
    _: User = Depends(require_permission("ver_menu")),
    db: AsyncSession = Depends(get_db),
):
    c = Categoria(
        restaurant_id=rid, nombre=body.nombre, descripcion=body.descripcion, foto=body.foto
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return CategoriaOut.model_validate(c)


@router.delete("/categorias/{categoria_id}", status_code=204)
async def delete_categoria(
    rid: str,
    categoria_id: str,
    _: User = Depends(require_permission("ver_menu")),
    db: AsyncSession = Depends(get_db),
):
    c = await db.get(Categoria, categoria_id)
    if c is None or c.restaurant_id != rid:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    n = await db.scalar(
        select(func.count()).select_from(Producto).where(Producto.categoria_id == categoria_id)
    )
    if n and n > 0:
        raise HTTPException(
            status_code=409,
            detail=f"La categoría tiene {n} producto(s). Elimínalos primero.",
        )
    await db.delete(c)
    await db.commit()


# ----------------- Productos -----------------
def producto_out(p: Producto) -> ProductoOut:
    return ProductoOut(
        id=p.id,
        nombre=p.nombre,
        precio=p.precio,
        categoria_id=p.categoria_id,
        foto=p.foto,
        visible=p.visible,
        ingredientes=[
            IngredienteRecetaOut(
                nombre=ing.nombre,
                obligatorio=ing.obligatorio,
                opciones=[OpcionRecetaOut(nombre=o.nombre) for o in ing.opciones],
            )
            for ing in p.ingredientes
        ],
        codigo_barras=p.codigo_barras,
        costo=p.costo or 0.0,
        controla_stock=bool(p.controla_stock),
        stock=p.stock or 0.0,
        stock_minimo=p.stock_minimo or 0.0,
        unidad=p.unidad or "und",
    )


async def get_producto_full(db: AsyncSession, rid: str, pid: str) -> Producto:
    result = await db.execute(
        select(Producto)
        .where(Producto.id == pid, Producto.restaurant_id == rid)
        .options(selectinload(Producto.ingredientes).selectinload(ProductoIngrediente.opciones))
    )
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return p


@router.get("/productos", response_model=list[ProductoOut])
async def list_productos(
    rid: str, _: User = Depends(require_restaurant_access), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Producto)
        .where(Producto.restaurant_id == rid)
        .options(selectinload(Producto.ingredientes).selectinload(ProductoIngrediente.opciones))
    )
    return [producto_out(p) for p in result.scalars().all()]


@router.post("/productos", response_model=ProductoOut, status_code=201)
async def add_producto(
    rid: str,
    body: ProductoCreate,
    current: User = Depends(require_permission("ver_menu")),
    db: AsyncSession = Depends(get_db),
):
    await _exigir_categoria(db, rid, body.categoria_id)
    codigo = normalizar_codigo(body.codigo_barras)
    await asegurar_codigo_libre(db, rid, codigo)
    p = Producto(
        restaurant_id=rid,
        nombre=body.nombre,
        precio=body.precio,
        categoria_id=body.categoria_id,
        foto=body.foto,
        visible=True,
        codigo_barras=codigo,
        costo=body.costo,
        controla_stock=body.controla_stock,
        stock=0.0,
        stock_minimo=body.stock_minimo,
        unidad=body.unidad,
    )
    for i, ing in enumerate(body.ingredientes):
        ing_model = ProductoIngrediente(nombre=ing.nombre, obligatorio=ing.obligatorio, orden=i)
        ing_model.opciones = [
            IngredienteOpcion(nombre=o.nombre, orden=j) for j, o in enumerate(ing.opciones)
        ]
        p.ingredientes.append(ing_model)
    db.add(p)
    await db.flush()
    if body.controla_stock and body.stock_inicial:
        mover_stock(
            db, p, "entrada", body.stock_inicial, nota="Stock inicial", usuario_id=current.id
        )
    await db.commit()
    return producto_out(await get_producto_full(db, rid, p.id))


async def _exigir_categoria(db: AsyncSession, rid: str, categoria_id: str) -> None:
    c = await db.get(Categoria, categoria_id)
    if c is None or c.restaurant_id != rid:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")


@router.patch("/productos/{producto_id}", response_model=ProductoOut)
async def update_producto(
    rid: str,
    producto_id: str,
    body: ProductoUpdate,
    _: User = Depends(require_permission("ver_menu")),
    db: AsyncSession = Depends(get_db),
):
    """Edita nombre, precios, código de barras, etc. El stock no se toca aquí."""
    p = await get_producto_full(db, rid, producto_id)
    cambios = body.model_dump(exclude_unset=True)
    if "codigo_barras" in cambios:
        cambios["codigo_barras"] = normalizar_codigo(cambios["codigo_barras"])
        await asegurar_codigo_libre(db, rid, cambios["codigo_barras"], excepto_id=p.id)
    if cambios.get("categoria_id") is not None:
        await _exigir_categoria(db, rid, cambios["categoria_id"])
    for campo, valor in cambios.items():
        if valor is None and campo != "codigo_barras" and campo != "foto":
            continue  # null en un campo obligatorio = no cambiar
        setattr(p, campo, valor)
    await db.commit()
    return producto_out(await get_producto_full(db, rid, producto_id))


@router.patch("/productos/{producto_id}/visible", response_model=ProductoOut)
async def toggle_visible(
    rid: str,
    producto_id: str,
    _: User = Depends(require_permission("ver_menu")),
    db: AsyncSession = Depends(get_db),
):
    p = await get_producto_full(db, rid, producto_id)
    p.visible = not p.visible
    await db.commit()
    return producto_out(await get_producto_full(db, rid, producto_id))


@router.delete("/productos/{producto_id}", status_code=204)
async def delete_producto(
    rid: str,
    producto_id: str,
    _: User = Depends(require_permission("ver_menu")),
    db: AsyncSession = Depends(get_db),
):
    p = await db.get(Producto, producto_id)
    if p is None or p.restaurant_id != rid:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    await db.delete(p)
    await db.commit()
