#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Las 26 consultas de database/03_consultas.sql reescritas en Python + pandas.

`cargar_tablas` hace la única parte con SQL (leer las tablas completas). Cada
función cNN recibe ese diccionario de tablas crudas y devuelve un DataFrame con
las mismas columnas que la consulta SQL equivalente. `ejecutar` corre ambas
versiones y las compara: el blog publica el código Python y el sello de que el
resultado coincide con la consulta SQL validada en la sustentación.
"""
import datetime as dt
import numbers
import time

import pandas as pd
from sqlalchemy import text

TABLAS = ("cliente", "empleado", "producto", "domicilio", "tipo_evento",
          "evento", "venta", "detalle_venta", "costo")


def cargar_tablas(cn):
    """Lee completas las 9 tablas del esquema `ventas` (único paso con SQL)."""
    return {n: pd.read_sql(text(f"SELECT * FROM ventas.{n}"), cn) for n in TABLAS}


# ---------------------------------------------------------------------------
# 26 consultas analíticas (una función por consulta del guion de clase)
# ---------------------------------------------------------------------------
def c01(t):
    """Resumen general: ventas, ingresos, ticket promedio y rango de fechas."""
    v = t["venta"]
    return pd.DataFrame([{
        "cantidad_ventas": len(v),
        "ingresos_totales": v.total_venta.sum(),
        "ticket_promedio": v.total_venta.mean(),
        "primera_venta": v.fecha_hora.min(),
        "ultima_venta": v.fecha_hora.max(),
    }])


def c02(t):
    """Ingresos y ticket promedio por canal de venta (Local / Domicilio)."""
    return (t["venta"].groupby("tipo_venta")
            .agg(cantidad_ventas=("total_venta", "size"),
                 ingresos=("total_venta", "sum"),
                 ticket_promedio=("total_venta", "mean"))
            .reset_index()
            .sort_values("ingresos", ascending=False)
            .reset_index(drop=True))


def c03(t):
    """Ventas e ingresos día por día."""
    v = t["venta"].assign(fecha=lambda d: d.fecha_hora.dt.date)
    return (v.groupby("fecha")
            .agg(cantidad_ventas=("total_venta", "size"),
                 ingresos=("total_venta", "sum"))
            .reset_index().sort_values("fecha").reset_index(drop=True))


def c04(t):
    """Ventas e ingresos por mes."""
    v = t["venta"].assign(mes=lambda d: d.fecha_hora.dt.to_period("M").dt.to_timestamp())
    return (v.groupby("mes")
            .agg(cantidad_ventas=("total_venta", "size"),
                 ingresos=("total_venta", "sum"))
            .reset_index().sort_values("mes").reset_index(drop=True))


def c05(t):
    """Ventas e ingresos por hora del día."""
    v = t["venta"].assign(hora=lambda d: d.fecha_hora.dt.hour)
    return (v.groupby("hora")
            .agg(cantidad_ventas=("total_venta", "size"),
                 ingresos=("total_venta", "sum"))
            .reset_index().sort_values("hora").reset_index(drop=True))


def c06(t):
    """Top 10 clientes por ingresos."""
    return (t["venta"].groupby("id_cliente")
            .agg(cantidad_ventas=("total_venta", "size"),
                 ingresos=("total_venta", "sum"))
            .reset_index()
            .merge(t["cliente"][["id_cliente", "nombre"]], on="id_cliente")
            [["id_cliente", "nombre", "cantidad_ventas", "ingresos"]]
            .sort_values("ingresos", ascending=False).head(10).reset_index(drop=True))


def c07(t):
    """Clientes que nunca han comprado (anti-join contra la tabla venta)."""
    con_venta = t["venta"].id_cliente.unique()
    return (t["cliente"].loc[~t["cliente"].id_cliente.isin(con_venta),
                             ["id_cliente", "nombre", "email"]]
            .sort_values("id_cliente").reset_index(drop=True))


def c08(t):
    """Ventas e ingresos gestionados por cada empleado (outer join a la izquierda)."""
    g = (t["venta"].groupby("id_empleado")
         .agg(ventas_registradas=("id_venta", "size"),
              ingresos_gestionados=("total_venta", "sum"),
              ticket_promedio=("total_venta", "mean")))
    r = t["empleado"].merge(g, on="id_empleado", how="left")
    r[["ventas_registradas", "ingresos_gestionados"]] = r[["ventas_registradas", "ingresos_gestionados"]].fillna(0)
    return (r[["id_empleado", "nombre", "cargo", "ventas_registradas", "ingresos_gestionados", "ticket_promedio"]]
            .sort_values("ingresos_gestionados", ascending=False, na_position="last")
            .reset_index(drop=True))


def c09(t):
    """Productos más vendidos por unidades y por ingresos."""
    return (t["producto"].merge(t["detalle_venta"], on="id_producto")
            .groupby(["id_producto", "nombre", "categoria"])
            .agg(unidades_vendidas=("cantidad", "sum"),
                 ingresos=("subtotal", "sum"))
            .reset_index()
            .sort_values(["unidades_vendidas", "ingresos"], ascending=[False, False])
            .reset_index(drop=True))


def c10(t):
    """Producto líder por ingresos (el de mayor facturación)."""
    return (t["producto"].merge(t["detalle_venta"], on="id_producto")
            .groupby(["id_producto", "nombre"])
            .agg(ingresos=("subtotal", "sum"))
            .reset_index()
            .sort_values("ingresos", ascending=False).head(1).reset_index(drop=True))


def c11(t):
    """Participación porcentual de cada producto en los ingresos totales."""
    d = t["detalle_venta"]
    r = (d.merge(t["producto"][["id_producto", "nombre"]], on="id_producto")
         .groupby("nombre")
         .agg(ingresos_producto=("subtotal", "sum"))
         .reset_index())
    r["participacion_pct"] = (100 * r.ingresos_producto / d.subtotal.sum()).round(2)
    return r.sort_values("participacion_pct", ascending=False).reset_index(drop=True)


def c12(t):
    """Rendimiento por categoría: unidades, ventas que la incluyen e ingresos."""
    return (t["producto"].merge(t["detalle_venta"], on="id_producto")
            .groupby("categoria")
            .agg(unidades_vendidas=("cantidad", "sum"),
                 ventas_con_categoria=("id_venta", "nunique"),
                 ingresos=("subtotal", "sum"))
            .reset_index()
            .sort_values("ingresos", ascending=False).reset_index(drop=True))


def c13(t):
    """Ticket promedio según cliente frecuente (100 o más compras)."""
    compras = t["venta"].groupby("id_cliente").size()
    cl = t["cliente"].assign(compras=lambda d: d.id_cliente.map(compras).fillna(0))
    cl["cliente_frecuente"] = cl.compras >= 100          # atributo derivado, no existe en la tabla
    return (t["venta"].merge(cl[["id_cliente", "cliente_frecuente"]], on="id_cliente")
            .groupby("cliente_frecuente")
            .agg(cantidad_ventas=("total_venta", "size"),
                 ticket_promedio=("total_venta", "mean"),
                 ingresos=("total_venta", "sum"))
            .reset_index()
            .sort_values("cliente_frecuente", ascending=False).reset_index(drop=True))


def c14(t):
    """Distribución de las ventas según la cantidad de líneas de detalle."""
    lineas = t["detalle_venta"].groupby("id_venta").size().rename("cantidad_lineas")
    v = t["venta"].merge(lineas, on="id_venta")
    return (v.groupby("cantidad_lineas")
            .agg(cantidad_ventas=("total_venta", "size"),
                 ticket_promedio=("total_venta", "mean"))
            .reset_index().sort_values("cantidad_lineas").reset_index(drop=True))


def c15(t):
    """Ventas a domicilio agrupadas por cliente y dirección de entrega."""
    v = t["venta"].loc[lambda d: d.tipo_venta == "Domicilio",
                       ["id_cliente", "id_domicilio", "total_venta"]]
    return (v.merge(t["domicilio"][["id_domicilio", "direccion_entrega"]], on="id_domicilio")
            .merge(t["cliente"][["id_cliente", "nombre"]], on="id_cliente")
            .groupby(["nombre", "direccion_entrega"])
            .agg(domicilios=("total_venta", "size"),
                 ingresos=("total_venta", "sum"))
            .reset_index()
            .sort_values(["domicilios", "ingresos"], ascending=[False, False])
            .reset_index(drop=True))


def c16(t):
    """Ingresos por canal comparando clientes frecuentes y no frecuentes."""
    compras = t["venta"].groupby("id_cliente").size()
    cl = t["cliente"].assign(compras=lambda d: d.id_cliente.map(compras).fillna(0))
    cl["cliente_frecuente"] = cl.compras >= 100
    return (t["venta"].merge(cl[["id_cliente", "cliente_frecuente"]], on="id_cliente")
            .groupby(["cliente_frecuente", "tipo_venta"])
            .agg(cantidad_ventas=("total_venta", "size"),
                 ingresos=("total_venta", "sum"))
            .reset_index()
            .sort_values(["cliente_frecuente", "ingresos"], ascending=[False, False])
            .reset_index(drop=True))


def c17(t):
    """Productos que nunca se han vendido."""
    vendidos = t["detalle_venta"].id_producto.unique()
    return (t["producto"].loc[~t["producto"].id_producto.isin(vendidos),
                              ["id_producto", "nombre", "categoria", "precio_venta"]]
            .sort_values("id_producto").reset_index(drop=True))


def c18(t):
    """Ventas cuyo total no coincide con la suma de sus líneas de detalle."""
    d = t["detalle_venta"].groupby("id_venta").agg(total_detalle=("subtotal", "sum"))
    r = t["venta"][["id_venta", "total_venta"]].merge(d, on="id_venta")
    r["diferencia"] = r.total_venta - r.total_detalle
    r = r.loc[r.total_venta != r.total_detalle]
    return r.sort_values("diferencia", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


def c19(t):
    """Clientes con eventos reservados y sus compras."""
    ev = t["evento"].groupby("id_cliente").size().rename("eventos_reservados")
    vc = (t["venta"].groupby("id_cliente")
          .agg(cantidad_ventas=("total_venta", "size"),
               ingresos=("total_venta", "sum")))
    r = (t["cliente"].merge(ev, on="id_cliente")
         .merge(vc, on="id_cliente", how="left")
         .fillna({"cantidad_ventas": 0, "ingresos": 0}))
    return (r[["id_cliente", "nombre", "eventos_reservados", "cantidad_ventas", "ingresos"]]
            .sort_values(["eventos_reservados", "ingresos"], ascending=[False, False])
            .reset_index(drop=True))


def c20(t):
    """Agenda de eventos con el tipo, la fecha y el cliente asociado."""
    e = t["evento"][["id_evento", "id_tipo_evento", "id_cliente",
                     "fecha", "hora_inicio", "hora_final", "ubicacion"]]
    r = (e.merge(t["tipo_evento"][["id_tipo_evento", "nombre"]]
                 .rename(columns={"nombre": "tipo_evento"}), on="id_tipo_evento")
         .merge(t["cliente"][["id_cliente", "nombre", "telefono"]]
                .rename(columns={"nombre": "cliente"}), on="id_cliente"))
    r = r[["id_evento", "tipo_evento", "fecha", "hora_inicio", "hora_final",
           "ubicacion", "id_cliente", "cliente", "telefono"]]
    return r.sort_values(["fecha", "hora_inicio"]).reset_index(drop=True)


def c21(t):
    """Eventos ejecutados e ingresos por tipo de evento."""
    g = (t["evento"].groupby("id_tipo_evento")
         .agg(eventos_ejecutados=("id_evento", "size"),
              ingresos_eventos=("valor_contratado", "sum")))
    r = t["tipo_evento"].merge(g, on="id_tipo_evento", how="left")
    r[["eventos_ejecutados", "ingresos_eventos"]] = r[["eventos_ejecutados", "ingresos_eventos"]].fillna(0)
    r["eventos_ejecutados"] = r.eventos_ejecutados.astype(int)
    return (r.rename(columns={"nombre": "tipo_evento"})
            [["id_tipo_evento", "tipo_evento", "eventos_ejecutados", "ingresos_eventos"]]
            .sort_values(["eventos_ejecutados", "ingresos_eventos", "tipo_evento"],
                         ascending=[False, False, True])
            .reset_index(drop=True))


def c22(t):
    """Costos por mes y tipo de costo."""
    k = t["costo"].assign(mes=lambda d: pd.to_datetime(d.fecha).dt.to_period("M").dt.to_timestamp())
    return (k.groupby(["mes", "tipo_costo"])
            .agg(costo_total=("monto", "sum"))
            .reset_index()
            .sort_values(["mes", "tipo_costo"]).reset_index(drop=True))


def c23(t):
    """Rentabilidad por producto: ingresos frente al costo de producción."""
    ing = (t["detalle_venta"].groupby("id_producto")
           .agg(unidades=("cantidad", "sum"), ingresos=("subtotal", "sum")))
    cst = (t["costo"].loc[lambda d: d.tipo_costo == "Producción"]
           .groupby("id_producto").agg(costo_produccion=("monto", "sum")))
    r = t["producto"].merge(ing, on="id_producto").merge(cst, on="id_producto", how="left")
    r["costo_produccion"] = r.costo_produccion.fillna(0)
    r["margen_bruto"] = r.ingresos - r.costo_produccion
    r["margen_pct"] = (100 * r.margen_bruto / r.ingresos.where(r.ingresos != 0)).round(2)
    return (r[["id_producto", "nombre", "categoria", "unidades", "ingresos",
               "costo_produccion", "margen_bruto", "margen_pct"]]
            .sort_values("margen_bruto", ascending=False).reset_index(drop=True))


def c24(t):
    """Estado de resultados mensual: ingresos menos producción y gastos operativos."""
    v = t["venta"].assign(mes=lambda d: d.fecha_hora.dt.to_period("M").dt.to_timestamp())
    ing = v.groupby("mes").agg(ingresos=("total_venta", "sum"))
    k = t["costo"].assign(mes=lambda d: pd.to_datetime(d.fecha).dt.to_period("M").dt.to_timestamp())
    cst = (k.pivot_table(index="mes", columns="tipo_costo", values="monto", aggfunc="sum")
            .rename(columns={"Producción": "costo_produccion",
                             "Operativo": "gastos_operativos"}))
    r = ing.join(cst, how="left").fillna({"costo_produccion": 0, "gastos_operativos": 0})
    r["utilidad"] = r.ingresos - r.costo_produccion - r.gastos_operativos
    r["margen_pct"] = (100 * r.utilidad / r.ingresos.where(r.ingresos != 0)).round(2)
    return (r.reset_index()[["mes", "ingresos", "costo_produccion", "gastos_operativos",
                             "utilidad", "margen_pct"]]
            .sort_values("mes").reset_index(drop=True))


def c25(t):
    """Rentabilidad por evento: valor contratado menos el costo del evento."""
    cst = (t["costo"].loc[lambda d: d.tipo_costo == "Evento"]
           .groupby("id_evento").agg(costo_evento=("monto", "sum")))
    r = (t["evento"][["id_evento", "id_tipo_evento", "id_cliente", "fecha", "valor_contratado"]]
         .merge(t["tipo_evento"][["id_tipo_evento", "nombre"]]
                .rename(columns={"nombre": "tipo_evento"}), on="id_tipo_evento")
         .merge(t["cliente"][["id_cliente", "nombre"]]
                .rename(columns={"nombre": "cliente"}), on="id_cliente")
         .merge(cst, on="id_evento", how="left"))
    r["costo_evento"] = r.costo_evento.fillna(0)
    r["utilidad"] = r.valor_contratado - r.costo_evento
    r["margen_pct"] = (100 * r.utilidad / r.valor_contratado.where(r.valor_contratado != 0)).round(2)
    return (r[["id_evento", "tipo_evento", "fecha", "cliente", "valor_contratado",
               "costo_evento", "utilidad", "margen_pct"]]
            .sort_values("fecha").reset_index(drop=True))


def c26(t):
    """Rentabilidad por categoría de producto."""
    ing = (t["detalle_venta"].merge(t["producto"][["id_producto", "categoria"]], on="id_producto")
           .groupby("categoria").agg(unidades=("cantidad", "sum"), ingresos=("subtotal", "sum")))
    cst = (t["costo"].loc[lambda d: d.tipo_costo == "Producción"]
           .merge(t["producto"][["id_producto", "categoria"]], on="id_producto")
           .groupby("categoria").agg(costo_produccion=("monto", "sum")))
    r = ing.join(cst, how="left")
    r["costo_produccion"] = r.costo_produccion.fillna(0)
    r["margen_pct"] = (100 * (r.ingresos - r.costo_produccion)
                       / r.ingresos.where(r.ingresos != 0)).round(2)
    return (r.reset_index()[["categoria", "unidades", "ingresos", "costo_produccion", "margen_pct"]]
            .sort_values("margen_pct", ascending=False).reset_index(drop=True))


PANDAS = {n: globals()[f"c{n:02d}"] for n in range(1, 27)}


# ---------------------------------------------------------------------------
# Validación: pandas vs. SQL
# ---------------------------------------------------------------------------
def _filas(df):
    """Filas del DataFrame como tuplas de texto comparable (fechas, nulls y decimales normalizados)."""
    filas = []
    for r in df.to_dict("records"):
        f = []
        for v in r.values():
            if v is None or v is pd.NaT or (isinstance(v, float) and v != v):
                f.append("")
            elif isinstance(v, bool):
                f.append(str(v))
            elif isinstance(v, pd.Timestamp):
                f.append(v.strftime("%Y-%m-%d"))
            elif isinstance(v, numbers.Number):
                f.append(f"{float(v):.4f}")
            elif isinstance(v, (dt.datetime, dt.date)):
                f.append(v.strftime("%Y-%m-%d"))
            else:
                f.append(str(v))
        filas.append(tuple(f))
    return filas


def comparar(pandas_df, sql_df):
    """Compara el resultado de pandas con el de la consulta SQL: (coincide, nota)."""
    if list(pandas_df.columns) != list(sql_df.columns):
        return False, f"columnas distintas: {list(pandas_df.columns)} vs {list(sql_df.columns)}"
    if len(pandas_df) != len(sql_df):
        return False, f"{len(pandas_df)} filas en pandas y {len(sql_df)} en SQL"
    a, b = _filas(pandas_df), _filas(sql_df)
    if a == b:
        return True, "idéntico al resultado SQL"
    if sorted(a) == sorted(b):
        return True, "mismos valores que el SQL (otro orden de filas)"
    i = next(k for k, (x, y) in enumerate(zip(a, b)) if x != y)
    return False, f"fila {i + 1} distinta: {a[i]} vs {b[i]}"


def ejecutar(cn, consultas):
    """Corre cada consulta en pandas y en SQL, y devuelve sus resultados y validación."""
    t = cargar_tablas(cn)
    salida = []
    for num, titulo, sql in consultas:
        fn = PANDAS[num]
        t0 = time.perf_counter()
        df = fn(t)
        ms = int((time.perf_counter() - t0) * 1000)
        ok, nota = comparar(df, pd.read_sql(text(sql), cn))
        salida.append(dict(num=num, titulo=titulo, codigo=fn, df=df, ms=ms, ok=ok, nota=nota))
        print(f"  consulta {num:2d}/26 {titulo[:38]:40s} -> {len(df):5d} filas · {ms:3d} ms · "
              f"{'OK' if ok else 'DIFIERE: ' + nota}")
    return salida
