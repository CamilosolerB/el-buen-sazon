"""Capa de acceso a datos: conexión a PostgreSQL y consultas SQL del análisis."""
import os, re, json
from urllib.parse import quote_plus
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()  # DATABASE_URL desde .env (también al ejecutar scripts CLI)

# ---------------------------------------------------------------------------
# CONSULTAS SQL (cada una alimenta una sección del informe)
# ---------------------------------------------------------------------------
QUERIES = {
# Resumen general y distribución del ticket (media, mediana, percentil 90, desviación).
"kpi": """
    SELECT COUNT(*) AS ventas, SUM(total_venta) AS ingresos, AVG(total_venta) AS ticket_prom,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_venta) AS ticket_mediana,
           PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY total_venta) AS ticket_p90,
           STDDEV_SAMP(total_venta) AS ticket_desv, COUNT(DISTINCT id_cliente) AS clientes,
           MIN(fecha_hora)::date AS desde, MAX(fecha_hora)::date AS hasta
    FROM ventas.venta""",
# Ventas e ingresos por mes y canal (Local / Domicilio).
"mes_canal": """
    SELECT TO_CHAR(fecha_hora,'YYYY-MM') AS m, tipo_venta AS canal, COUNT(*) AS v, SUM(total_venta) AS i
    FROM ventas.venta GROUP BY 1,2""",
# Comportamiento por hora del día.
"hora": """
    SELECT TO_CHAR(fecha_hora,'YYYY-MM') AS m, EXTRACT(HOUR FROM fecha_hora)::int AS h, COUNT(*) AS v, SUM(total_venta) AS i
    FROM ventas.venta GROUP BY 1,2""",
# Comportamiento por día de la semana (1 = lunes ... 7 = domingo).
"dia": """
    SELECT TO_CHAR(fecha_hora,'YYYY-MM') AS m, EXTRACT(ISODOW FROM fecha_hora)::int AS d, COUNT(*) AS v, SUM(total_venta) AS i
    FROM ventas.venta GROUP BY 1,2""",
# Unidades e ingresos por producto y mes (detalle de venta).
"producto": """
    SELECT TO_CHAR(v.fecha_hora,'YYYY-MM') AS m, p.id_producto, p.nombre AS n, p.categoria AS c,
           SUM(d.cantidad) AS u, SUM(d.subtotal) AS i
    FROM ventas.detalle_venta d
    JOIN ventas.venta v ON v.id_venta = d.id_venta
    JOIN ventas.producto p ON p.id_producto = d.id_producto
    GROUP BY 1,2,3,4""",
# Costo de producción por producto y mes (tabla costo, tipo 'Producción').
"costo_prod": """
    SELECT TO_CHAR(fecha,'YYYY-MM') AS m, id_producto, SUM(monto) AS k
    FROM ventas.costo WHERE tipo_costo = 'Producción' GROUP BY 1,2""",
# Gastos operativos por concepto y mes (tabla costo, tipo 'Operativo').
"operativo": """
    SELECT TO_CHAR(fecha,'YYYY-MM') AS m, REGEXP_REPLACE(concepto,' \\d{4}-\\d{2}$','') AS c, SUM(monto) AS k
    FROM ventas.costo WHERE tipo_costo = 'Operativo' GROUP BY 1,2""",
# Clientes: ventas e ingresos por cliente y mes.
"cliente": """
    SELECT TO_CHAR(v.fecha_hora,'YYYY-MM') AS m, c.nombre || ' (#' || c.id_cliente || ')' AS n,
           COUNT(*) AS v, SUM(v.total_venta) AS i
    FROM ventas.venta v JOIN ventas.cliente c ON c.id_cliente = v.id_cliente GROUP BY 1,2""",
# Empleados: ventas gestionadas por empleado y mes.
"empleado": """
    SELECT TO_CHAR(v.fecha_hora,'YYYY-MM') AS m, e.nombre AS n, e.cargo AS g, COUNT(*) AS v, SUM(v.total_venta) AS i
    FROM ventas.venta v JOIN ventas.empleado e ON e.id_empleado = v.id_empleado GROUP BY 1,2,3""",
# Tasa de acompañamiento: ventas que incluyen cada categoría de producto.
"categoria_venta": """
    SELECT TO_CHAR(v.fecha_hora,'YYYY-MM') AS m, p.categoria AS c, COUNT(DISTINCT d.id_venta) AS v
    FROM ventas.detalle_venta d
    JOIN ventas.venta v ON v.id_venta = d.id_venta
    JOIN ventas.producto p ON p.id_producto = d.id_producto GROUP BY 1,2""",
# Eventos ejecutados con su tipo, valor contratado, costo y utilidad.
"eventos": """
    SELECT e.id_evento, t.nombre AS tipo, e.fecha::text AS fecha, c.nombre AS cliente,
           e.valor_contratado AS valor, COALESCE(SUM(k.monto),0) AS costo
    FROM ventas.evento e
    JOIN ventas.tipo_evento t ON t.id_tipo_evento = e.id_tipo_evento
    JOIN ventas.cliente c ON c.id_cliente = e.id_cliente
    LEFT JOIN ventas.costo k ON k.id_evento = e.id_evento AND k.tipo_costo = 'Evento'
    GROUP BY e.id_evento, t.nombre, e.fecha, c.nombre, e.valor_contratado ORDER BY e.fecha""",
# Catálogo de tipos de evento y cuántos se han ejecutado.
"tipos_evento": """
    SELECT t.nombre AS tipo, COUNT(e.id_evento) AS n
    FROM ventas.tipo_evento t LEFT JOIN ventas.evento e ON e.id_tipo_evento = t.id_tipo_evento
    GROUP BY t.nombre ORDER BY n DESC, t.nombre""",
}

# ---------------------------------------------------------------------------
# CONEXIÓN Y EXTRACCIÓN
# ---------------------------------------------------------------------------
def conectar():
    """Prioriza DATABASE_URL (Supabase/Render/Railway); si no existe usa las variables PG*."""
    url = os.getenv("DATABASE_URL")
    if url:
        url = re.sub(r"^postgres(ql)?://", "postgresql+psycopg2://", url)
        kw = {"connect_args": {"sslmode": "require"}} if "supabase" in url else {}
        return create_engine(url, pool_pre_ping=True, **kw)
    g = lambda k, d: os.getenv(k, d)
    url = (f"postgresql+psycopg2://{g('PGUSER','postgres')}:{quote_plus(g('PGPASSWORD',''))}"
           f"@{g('PGHOST','localhost')}:{g('PGPORT','5432')}/{g('PGDATABASE','el_buen_sabor')}")
    return create_engine(url)

def extraer(engine):
    dfs = {}
    with engine.connect() as cn:
        for nombre, sql in QUERIES.items():
            df = pd.read_sql(text(sql), cn)
            for c in df.columns:                       # Decimal -> float
                if df[c].dtype == object:
                    try: df[c] = pd.to_numeric(df[c])
                    except (ValueError, TypeError): pass
            dfs[nombre] = df
            print(f"  consulta {nombre:16s} -> {len(df)} filas")
    return dfs

def rows(df): return json.loads(df.to_json(orient="records", date_format="iso"))
