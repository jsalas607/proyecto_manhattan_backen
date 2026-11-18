"""Reglas de stock compartidas por ventas, entradas, salidas, ajustes e importación.

Todo cambio de `Producto.stock` pasa por `mover_stock`, así el kárdex
(`stock_movimientos`) siempre cuadra con el stock actual.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Producto
from app.models.stock import StockMovimiento


def normalizar_codigo(codigo: str | None) -> str | None:
    """Quita espacios; un código vacío se guarda como NULL."""
    if codigo is None:
        return None
    codigo = codigo.strip()
    return codigo or None


async def asegurar_codigo_libre(
    db: AsyncSession, rid: str, codigo: str | None, excepto_id: str | None = None
) -> None:
    """409 si otro producto del restaurante ya usa ese código de barras."""
    if codigo is None:
        return
    q = select(Producto.nombre).where(
        Producto.restaurant_id == rid, Producto.codigo_barras == codigo
    )
    if excepto_id is not None:
        q = q.where(Producto.id != excepto_id)
    otro = await db.scalar(q.limit(1))
    if otro is not None:
        raise HTTPException(
            status_code=409, detail=f"El código {codigo} ya lo usa el producto «{otro}»"
        )


async def productos_por_id(
    db: AsyncSession, rid: str, ids: list[str], *, bloquear: bool = True
) -> dict[str, Producto]:
    """Carga los productos del restaurante. Con `bloquear`, los toma con
    SELECT ... FOR UPDATE para que dos ventas simultáneas no pisen el stock."""
    if not ids:
        return {}
    q = select(Producto).where(Producto.restaurant_id == rid, Producto.id.in_(set(ids)))
    if bloquear:
        q = q.with_for_update()
    result = await db.execute(q)
    return {p.id: p for p in result.scalars().all()}


async def exigir_productos(db: AsyncSession, rid: str, ids: list[str]) -> dict[str, Producto]:
    """Como `productos_por_id`, pero 404 si alguno no es de este restaurante."""
    prods = await productos_por_id(db, rid, ids)
    faltan = [i for i in ids if i not in prods]
    if faltan:
        raise HTTPException(status_code=404, detail=f"Producto no encontrado: {faltan[0]}")
    return prods


def mover_stock(
    db: AsyncSession,
    producto: Producto,
    tipo: str,
    cantidad: float,
    *,
    costo_unitario: float | None = None,
    motivo: str = "",
    nota: str = "",
    venta_id: str | None = None,
    usuario_id: str | None = None,
) -> StockMovimiento:
    """Suma `cantidad` (con signo) al stock y deja el movimiento en el kárdex.
    El stock puede quedar negativo: es preferible vender lo que hay en la
    nevera aunque el conteo esté desfasado; el reporte lo señala."""
    producto.stock = (producto.stock or 0.0) + cantidad
    mov = StockMovimiento(
        restaurant_id=producto.restaurant_id,
        producto_id=producto.id,
        tipo=tipo,
        cantidad=cantidad,
        stock_resultante=producto.stock,
        costo_unitario=producto.costo if costo_unitario is None else costo_unitario,
        motivo=motivo,
        nota=nota,
        venta_id=venta_id,
        usuario_id=usuario_id,
    )
    db.add(mov)
    return mov


def costo_promedio(stock: float, costo: float, cantidad: float, costo_nuevo: float) -> float:
    """Costo promedio ponderado tras una compra. Si no había stock (o era
    negativo), el costo pasa a ser el de la compra."""
    if stock <= 0 or costo <= 0:
        return costo_nuevo
    return (stock * costo + cantidad * costo_nuevo) / (stock + cantidad)

