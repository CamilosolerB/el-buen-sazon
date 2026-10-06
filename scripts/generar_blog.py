#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blog del proyecto de aula - Análisis descriptivo (El Buen Sazón).
Usa la conexión y consultas de analisis_descriptivo.py, agrega consultas propias,
construye DataFrames con pandas y escribe blog_el_buen_sazon.html.
Uso: PGPASSWORD=clave python generar_blog.py"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import html, calendar, datetime as dt, re, time, inspect
import pandas as pd
from sqlalchemy import text
from app.db import conectar, extraer, QUERIES
from app.informe import cop, ent, DIAS, MESES

BASE = pathlib.Path(__file__).resolve().parent.parent
ARCHIVO_SQL = BASE / "database" / "03_consultas.sql"

EXTRA = {
# Todos los tickets para estadísticos descriptivos por canal (describe()).
"ticket": "SELECT tipo_venta, total_venta FROM ventas.venta",
# Registros por tabla (sección Conjunto de datos).
"tablas": """SELECT 'cliente' AS t, COUNT(*) AS n FROM ventas.cliente UNION ALL SELECT 'empleado', COUNT(*) FROM ventas.empleado
  UNION ALL SELECT 'producto', COUNT(*) FROM ventas.producto UNION ALL SELECT 'domicilio', COUNT(*) FROM ventas.domicilio
  UNION ALL SELECT 'tipo_evento', COUNT(*) FROM ventas.tipo_evento UNION ALL SELECT 'evento', COUNT(*) FROM ventas.evento
  UNION ALL SELECT 'venta', COUNT(*) FROM ventas.venta UNION ALL SELECT 'detalle_venta', COUNT(*) FROM ventas.detalle_venta
  UNION ALL SELECT 'costo', COUNT(*) FROM ventas.costo""",
# Controles de calidad de datos (consultas 7, 17 y 18 del script de consultas).
"calidad": """SELECT (SELECT COUNT(*) FROM ventas.cliente c WHERE NOT EXISTS (SELECT 1 FROM ventas.venta v WHERE v.id_cliente=c.id_cliente)) AS cli_sin_compras,
  (SELECT COUNT(*) FROM (SELECT v.id_venta FROM ventas.venta v JOIN ventas.detalle_venta d USING (id_venta)
        GROUP BY v.id_venta, v.total_venta HAVING v.total_venta <> SUM(d.subtotal)) x) AS ventas_descuadradas,
  (SELECT COUNT(*) FROM ventas.producto p WHERE NOT EXISTS (SELECT 1 FROM ventas.detalle_venta d WHERE d.id_producto=p.id_producto)) AS prod_sin_ventas""",
}
SNIPPET = '''from sqlalchemy import create_engine, text
import pandas as pd

engine = create_engine("postgresql+psycopg2://usuario:clave@localhost:5432/el_buen_sabor")
with engine.connect() as cn:
    df_ventas = pd.read_sql(text("""
        SELECT TO_CHAR(fecha_hora,'YYYY-MM') AS mes, tipo_venta AS canal,
               COUNT(*) AS ventas, SUM(total_venta) AS ingresos
        FROM ventas.venta GROUP BY 1,2"""), cn)

df_ventas.groupby("mes")[["ventas", "ingresos"]].sum()      # agrupar
df_ventas["ingresos"].describe()                            # estadísticos descriptivos'''

m0 = lambda n: "$" + f"{n:,.0f}".replace(",", ".")
pc = lambda x: f"{x:.1f} %".replace(".", ",")
MM = lambda m: f"{MESES[int(m[5:])][:3].capitalize()} {m[2:4]}"
def tabla(df, fm={}):
    th = "".join(f"<th>{c}</th>" for c in df.columns)
    tr = "".join("<tr>" + "".join(f"<td>{fm.get(c, str)(v)}</td>" for c, v in r.items()) + "</tr>" for r in df.to_dict("records"))
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'
def hbar(items, fm, color="var(--ac)"):
    mx = max(abs(v) for _, v in items) or 1
    return '<div class="hb">' + "".join(f'<div><span>{html.escape(str(l))}</span><i><b style="width:{abs(v)/mx*100:.1f}%;background:{color}"></b></i><em>{fm(v)}</em></div>' for l, v in items) + "</div>"
def vbar(items, fm):
    mx = max(v for _, v in items) or 1
    return '<div class="vb">' + "".join(f'<div><em>{fm(v)}</em><i><b style="height:{v/mx*100:.1f}%"></b></i><span>{l}</span></div>' for l, v in items) + "</div>"
def kpi(n, titulo, nombre, df, tab, graf, concl):
    return (f'<article><h3>KPI {n} · {titulo}</h3><p class="df">DataFrame <code>{nombre}</code> · {df.shape[0]} filas × {df.shape[1]} columnas</p>'
            f'{tab}<div class="ch">{graf}</div><p class="cn"><b>Conclusión.</b> {concl}</p></article>')

# ---------------------------------------------------------------------------
# Bloques de código estilo carbon.now.sh (autocontenido: sin CDN ni librerías)
# ---------------------------------------------------------------------------
PALABRAS = {
 "sql": "SELECT|FROM|WHERE|GROUP|BY|ORDER|LIMIT|OFFSET|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|AND|OR|NOT|IN|IS|NULL|"
        "DISTINCT|UNION|ALL|CASE|WHEN|THEN|ELSE|END|BETWEEN|LIKE|ASC|DESC|WITHIN|OVER|PARTITION|INTERVAL|"
        "COUNT|SUM|AVG|MIN|MAX|COALESCE|PERCENTILE_CONT|STDDEV_SAMP|TO_CHAR|DATE_TRUNC|EXTRACT|REGEXP_REPLACE|CAST|ROUND",
 "python": "def|return|import|from|as|if|elif|else|for|while|in|not|and|or|None|True|False|lambda|with|try|except|"
           "class|print|open|len|range|str|int|float|list|dict|set|enumerate|sorted|max|min|sum|abs|round|yield|global",
}
PATRONES = {k: re.compile(
    r"(?P<c>--[^\n]*|#[^\n]*)"
    r"|(?P<s>'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"
    rf"|(?P<k>\b(?:{PALABRAS[k]})\b)"
    r"|(?P<n>\b\d+(?:\.\d+)?\b)") for k in PALABRAS}

def _linea(ln, lang):
    """Aplica resaltado de sintaxis a una línea ya sin escapar y devuelve su HTML."""
    pat, pos, out = PATRONES[lang], 0, []
    for m in pat.finditer(ln):
        out.append(html.escape(ln[pos:m.start()]))
        out.append(f'<span class="t-{m.lastgroup}">{html.escape(m.group(0))}</span>')
        pos = m.end()
    out.append(html.escape(ln[pos:]))
    return "".join(out)

def carbon(code, archivo, lang="sql"):
    """Bloque carbon: panel oscuro, semáforo, nombre de archivo, números de línea y resaltado."""
    lineas = [_linea(l, lang) for l in code.strip("\n").split("\n")]
    cuerpo = "".join(f'<span class="ln">{n}</span>{l}\n' for n, l in enumerate(lineas, 1))
    return (f'<div class="carbon"><div class="cb-top"><span class="cb-dots"><i></i><i></i><i></i></span>'
            f'<span class="cb-file">{html.escape(archivo)}</span><span class="cb-lang">{lang.upper()}</span></div>'
            f'<pre class="cb-code"><code>{cuerpo}</code></pre></div>')

def fm_resultado(df):
    """Formato numérico automático para las tablas de resultado (es-CO)."""
    dec = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    fm = {}
    for c in df.columns:
        s = df[c].dropna()
        if not len(s): continue
        v = s.iloc[0]
        if pd.api.types.is_integer_dtype(df[c]): fm[c] = ent
        elif pd.api.types.is_float_dtype(df[c]): fm[c] = dec
        elif hasattr(v, "strftime"): fm[c] = lambda x: x.strftime("%Y-%m-%d")
        else: fm[c] = lambda x: html.escape(str(x))
    return fm

def tabla_resultado(df, limite=12):
    """Tabla del resultado (primeras `limite` filas) con nota cuando se trunca o no hay filas."""
    visto = df.head(limite)
    t = tabla(visto, fm_resultado(visto))
    if not len(df):
        t += '<p class="nt"><b>0 filas:</b> la consulta no devuelve resultados (no hay casos que listar).</p>'
    elif len(df) > len(visto):
        t += f'<p class="nt">Mostrando las primeras {len(visto)} de {len(df)} filas.</p>'
    return t

def leer_consultas():
    """Parsea database/03_consultas.sql y devuelve [(número, título, SQL), ...] (26 consultas)."""
    partes = re.split(r"(?m)^--\s*(\d+)\.\s*(.+)$", ARCHIVO_SQL.read_text(encoding="utf-8"))
    return [(int(partes[i]), partes[i + 1].strip(), partes[i + 2].strip())
            for i in range(1, len(partes), 3)]

# Agrupación temática de las 26 consultas (número -> sección del blog)
GRUPOS = [
 ("Ventas y demanda", "g-ventas", [1, 2, 3, 4, 5]),
 ("Clientes, empleados y domicilios", "g-clientes", [6, 7, 8, 13, 14, 15, 16]),
 ("Productos y categorías", "g-productos", [9, 10, 11, 12, 17]),
 ("Consistencia de los datos", "g-calidad", [18]),
 ("Eventos", "g-eventos", [19, 20, 21]),
 ("Costos y rentabilidad", "g-costos", [22, 23, 24, 25, 26]),
]

def ejecutar_consultas(cn, consultas):
    """Ejecuta cada consulta y devuelve el HTML: bloque carbon + resultado."""
    htmls = {}
    for num, titulo, sql in consultas:
        t0 = time.perf_counter()
        df = pd.read_sql(text(sql), cn)
        ms = int((time.perf_counter() - t0) * 1000)
        meta = (f'<p class="df">Resultado · DataFrame <code>consulta_{num:02d}</code> · '
                f'{len(df)} fila{"s" if len(df) != 1 else ""} × {df.shape[1]} columnas · {ms} ms</p>')
        htmls[num] = (f'<article class="q"><h4 id="q{num}">Consulta {num} · {html.escape(titulo)}</h4>'
                      f'{carbon(sql, "03_consultas.sql", "sql")}{meta}{tabla_resultado(df)}</article>')
        print(f"  consulta {num:2d}/26 {titulo[:40]:42s} -> {len(df):5d} filas · {ms} ms")
    return htmls

def secciones_consultas(htmls):
    """Agrupa las consultas por tema con anclas navegables."""
    out = []
    for titulo, cid, nums in GRUPOS:
        usados = [n for n in nums if n in htmls]
        if not usados: continue
        out.append(f'<h4 class="gq" id="{cid}">{titulo} <span class="nt">({len(usados)} consultas)</span></h4>')
        out += [htmls[n] for n in sorted(usados)]
    faltan = sorted(set(htmls) - {n for _, _, ns in GRUPOS for n in ns})
    out += [htmls[n] for n in faltan]
    return "".join(out)


def main():
    eng = conectar(); d = extraer(eng)
    with eng.connect() as cn:
        for k, q in EXTRA.items(): d[k] = pd.read_sql(text(q), cn)
        qhtml = secciones_consultas(ejecutar_consultas(cn, leer_consultas()))
    # código mostrado en Carbon (se calcula antes del f-string: sus fuentes llaman {})
    src_con = carbon(inspect.getsource(conectar), "app/db.py", "python")
    src_ext = carbon(inspect.getsource(extraer), "app/db.py", "python")
    src_snip = carbon(SNIPPET, "conexion_ejemplo.py", "python")
    k = d["kpi"].iloc[0]; desde, hasta = pd.Timestamp(k.desde), pd.Timestamp(k.hasta)
    mc = d["mes_canal"]; ING = mc.i.sum(); VT = mc.v.sum()

    # --- DF1 ventas por mes
    def dias(m):
        y, mo = int(m[:4]), int(m[5:]); a = max(pd.Timestamp(y, mo, 1), desde); b = min(pd.Timestamp(y, mo, calendar.monthrange(y, mo)[1]), hasta)
        return (b - a).days + 1
    men = mc.groupby("m").agg(ventas=("v", "sum"), ingresos=("i", "sum")).reset_index()
    men["dias"] = men.m.map(dias); men["ticket"] = men.ingresos / men.ventas; men["ingreso_dia"] = men.ingresos / men.dias
    df_mensual = men.rename(columns={"m": "mes", "ingreso_dia": "ingreso diario", "ticket": "ticket promedio"})[["mes", "ventas", "ingresos", "dias", "ticket promedio", "ingreso diario"]]
    comp = men.iloc[1:-1]; best = comp.loc[comp.ingreso_dia.idxmax()]; low = comp.loc[comp.ingreso_dia.idxmin()]
    t1 = kpi(1, "Ventas e ingresos por mes", "df_mensual", df_mensual,
        tabla(df_mensual, {"mes": lambda m: MM(m), "ventas": ent, "ingresos": m0, "ticket promedio": m0, "ingreso diario": m0}),
        vbar([(MM(r.m), r.ingreso_dia) for r in men.itertuples()], cop),
        f"Febrero y septiembre son meses parciales, por eso se compara el ingreso diario. Entre los meses completos el mejor fue {MESES[int(best.m[5:])]} ({cop(best.ingreso_dia)} por día) y el más bajo {MESES[int(low.m[5:])]} ({cop(low.ingreso_dia)}); la diferencia es de {pc(100*(best.ingreso_dia/low.ingreso_dia-1))}, es decir, la demanda es estable.")

    # --- DF2 canal + estadísticos del ticket
    st = d["ticket"].groupby("tipo_venta").total_venta.describe(percentiles=[.5, .9])
    cn_ = mc.groupby("canal").agg(ventas=("v", "sum"), ingresos=("i", "sum")).join(st[["mean", "50%", "90%", "std"]]).reset_index()
    cn_["% ingresos"] = 100 * cn_.ingresos / ING
    df_canal = cn_.rename(columns={"canal": "canal", "mean": "ticket medio", "50%": "mediana", "90%": "percentil 90", "std": "desv. estándar"})[["canal", "ventas", "ingresos", "% ingresos", "ticket medio", "mediana", "percentil 90", "desv. estándar"]]
    loc_, dom = [df_canal[df_canal.canal == c].iloc[0] for c in ("Local", "Domicilio")]
    t2 = kpi(2, "Canal de venta y distribución del ticket", "df_canal", df_canal,
        tabla(df_canal, {"ventas": ent, "ingresos": m0, "% ingresos": pc, "ticket medio": m0, "mediana": m0, "percentil 90": m0, "desv. estándar": m0}),
        hbar([(r.canal, r.ingresos) for r in df_canal.itertuples()], cop, "var(--bl)"),
        f"El canal Local concentra {pc(loc_['% ingresos'])} de los ingresos, pero el ticket del domicilio ({m0(dom['ticket medio'])}) es {pc(100*(dom['ticket medio']/loc_['ticket medio']-1))} mayor al local ({m0(loc_['ticket medio'])}). La media supera a la mediana en ambos canales: hay pocos tickets altos que jalonan el promedio.")

    # --- DF3 hora y día
    hh = d["hora"].groupby("h").agg(ventas=("v", "sum")).reset_index(); hh["pct"] = 100 * hh.ventas / VT
    dd = d["dia"].groupby("d").agg(ventas=("v", "sum"), ingresos=("i", "sum")).reset_index(); dd["% ventas"] = 100 * dd.ventas / VT
    df_dia = dd.assign(día=dd.d.map(lambda i: DIAS[i-1].capitalize()))[["día", "ventas", "ingresos", "% ventas"]]
    top3 = hh.nlargest(3, "ventas"); bot3 = hh.nsmallest(3, "ventas")
    t3 = kpi(3, "Demanda por hora y día de la semana", "df_dia", df_dia,
        tabla(df_dia, {"ventas": ent, "ingresos": m0, "% ventas": pc}), vbar([(f"{r.h}h", r.ventas) for r in hh.itertuples()], ent),
        f"Las horas {', '.join(str(int(h))+':00' for h in top3.h)} concentran {pc(top3.pct.sum())} de las ventas; las tres de menor movimiento ({', '.join(str(int(h))+':00' for h in bot3.h)}) apenas aportan {pc(bot3.pct.sum())}. El día fuerte es el {DIAS[int(dd.loc[dd.ventas.idxmax(), 'd'])-1]} y el más flojo el {DIAS[int(dd.loc[dd.ventas.idxmin(), 'd'])-1]}.")

    # --- DF4 productos y categorías
    p = d["producto"].merge(d["costo_prod"], on=["m", "id_producto"], how="left").fillna({"k": 0})
    pr = p.groupby(["n", "c"]).agg(u=("u", "sum"), i=("i", "sum"), k=("k", "sum")).reset_index().sort_values("i", ascending=False)
    pr["mg"] = 100 * (pr.i - pr.k) / pr.i; pr["sh"] = 100 * pr.i / pr.i.sum()
    df_prod = pr.rename(columns={"n": "producto", "c": "categoría", "u": "unidades", "i": "ingresos", "k": "costo producción", "mg": "margen bruto %", "sh": "% ingresos"})
    lo = pr.sort_values("mg").iloc[0]; hi = pr.sort_values("mg").iloc[-1]
    t4 = kpi(4, "Productos: ventas y margen bruto", "df_prod", df_prod,
        tabla(df_prod, {"unidades": ent, "ingresos": m0, "costo producción": m0, "margen bruto %": pc, "% ingresos": pc}),
        hbar([(r.n, r.mg) for r in pr.sort_values("mg", ascending=False).itertuples()], pc),
        f"{pr.iloc[0].n} lidera los ingresos ({pc(pr.iloc[0].sh)}). El producto con mayor margen es {hi.n} ({pc(hi.mg)}) y el de menor margen {lo.n} ({pc(lo.mg)}): vender más unidades no implica más utilidad.")
    ca = pr.groupby("c").agg(u=("u", "sum"), i=("i", "sum"), k=("k", "sum")).reset_index(); ca["mg"] = 100 * (ca.i - ca.k) / ca.i
    cv = d["categoria_venta"].groupby("c").v.sum(); ca["inc"] = ca.c.map(lambda c: 100 * cv.get(c, 0) / VT)
    df_cat = ca.sort_values("i", ascending=False).rename(columns={"c": "categoría", "u": "unidades", "i": "ingresos", "k": "costo producción", "mg": "margen bruto %", "inc": "% de ventas que la incluyen"})
    t5 = kpi(5, "Categorías y venta cruzada", "df_cat", df_cat,
        tabla(df_cat, {"unidades": ent, "ingresos": m0, "costo producción": m0, "margen bruto %": pc, "% de ventas que la incluyen": pc}),
        hbar([(r.c, r.inc) for r in ca.sort_values("inc", ascending=False).itertuples()], pc, "var(--ok)"),
        f"Solo {pc(ca.set_index('c').inc.get('Gaseosa', 0))} de las ventas incluye gaseosa, {pc(ca.set_index('c').inc.get('Acompañante', 0))} un acompañante y {pc(ca.set_index('c').inc.get('Cerveza', 0))} cerveza: la venta cruzada es la principal oportunidad de ticket.")

    # --- DF6 clientes
    cl = d["cliente"].groupby("n").agg(v=("v", "sum"), i=("i", "sum")).sort_values("i", ascending=False).reset_index(); cl["sh"] = 100 * cl.i / cl.i.sum()
    df_cli = cl.head(10).rename(columns={"n": "cliente", "v": "ventas", "i": "ingresos", "sh": "% ingresos"})
    fr = cl[cl.v >= 100]
    t6 = kpi(6, "Clientes: concentración de ingresos", "df_cli", df_cli, tabla(df_cli, {"ventas": ent, "ingresos": m0, "% ingresos": pc}),
        hbar([(r.cliente, r.ingresos) for r in df_cli.itertuples()], cop),
        f"{len(fr)} de {len(cl)} clientes (con 100 o más compras) generan {pc(fr.sh.sum())} de los ingresos. La mediana de compras por cliente es {ent(cl.v.median())} y el promedio {ent(cl.v.mean())}: hay un grupo muy fiel y una cola larga de compradores ocasionales.")

    # --- DF7 empleados
    em = d["empleado"].groupby(["n", "g"]).agg(v=("v", "sum"), i=("i", "sum")).reset_index(); em["t"] = em.i / em.v; em["sh"] = 100 * em.i / em.i.sum()
    df_emp = em.sort_values("i", ascending=False).rename(columns={"n": "empleado", "g": "cargo", "v": "ventas", "i": "ingresos", "t": "ticket promedio", "sh": "% ingresos"})
    t7 = kpi(7, "Empleados: ventas gestionadas", "df_emp", df_emp, tabla(df_emp, {"ventas": ent, "ingresos": m0, "ticket promedio": m0, "% ingresos": pc}),
        hbar([(r.empleado, r.ingresos) for r in df_emp.itertuples()], cop, "var(--bl)"),
        f"{df_emp.iloc[0].empleado} gestiona {pc(df_emp.iloc[0]['% ingresos'])} de los ingresos y {df_emp.iloc[-1].empleado} {pc(df_emp.iloc[-1]['% ingresos'])}; el ticket promedio es similar entre empleados ({m0(em.t.min())} a {m0(em.t.max())}), de modo que la diferencia está en el volumen y no en la calidad de la venta.")

    # --- DF8 rentabilidad mensual y gastos
    cp = d["costo_prod"].groupby("m").k.sum(); op = d["operativo"].groupby("m").k.sum()
    pl = men.set_index("m")[["ingresos"]].assign(cp=cp, op=op); pl["ut"] = pl.ingresos - pl.cp - pl.op; pl["mg"] = 100 * pl.ut / pl.ingresos
    df_pl = pl.reset_index().rename(columns={"m": "mes", "cp": "costo producción", "op": "gastos operativos", "ut": "utilidad", "mg": "margen neto %"})
    CP, OP = cp.sum(), op.sum(); UT = ING - CP - OP; be = (OP / (1 - CP / ING)) / len(comp.index) if False else None
    mbp = 1 - CP / ING; be_mes = (comp.shape[0] and (op.loc[comp.m].mean() / mbp))
    t8 = kpi(8, "Rentabilidad: estado de resultados mensual", "df_pl", df_pl,
        tabla(df_pl, {"mes": MM, "ingresos": m0, "costo producción": m0, "gastos operativos": m0, "utilidad": m0, "margen neto %": pc}),
        vbar([(MM(r.m), r.mg) for r in pl.reset_index().itertuples()], pc),
        f"Utilidad total de {cop(UT)} (margen neto {pc(100*UT/ING)}): el costo de producción consume {pc(100*CP/ING)} de los ingresos y los gastos operativos {pc(100*OP/ING)}. El punto de equilibrio mensual es de aproximadamente {cop(be_mes)}, frente a {cop(comp.ingresos.mean())} de ventas promedio en los meses completos.")
    gs = d["operativo"].groupby("c").k.sum().sort_values(ascending=False).reset_index(); gs["sh"] = 100 * gs.k / gs.k.sum()
    df_gas = gs.rename(columns={"c": "concepto", "k": "monto", "sh": "% de gastos"})
    t9 = kpi(9, "Gastos operativos por concepto", "df_gas", df_gas, tabla(df_gas, {"monto": m0, "% de gastos": pc}),
        hbar([(r.concepto, r.monto) for r in df_gas.itertuples()], cop, "#8a5a00"),
        f"{df_gas.iloc[0].concepto} es el mayor gasto ({pc(df_gas.iloc[0]['% de gastos'])}), seguido de {df_gas.iloc[1].concepto} ({pc(df_gas.iloc[1]['% de gastos'])}).")

    # --- DF10 eventos
    ev = d["eventos"].copy(); ev["utilidad"] = ev.valor - ev.costo; ev["margen %"] = 100 * ev.utilidad / ev.valor
    df_ev = ev.rename(columns={"valor": "valor contratado", "costo": "costo del evento"}).drop(columns="id_evento")
    t10 = kpi(10, "Eventos por tipo", "df_ev", df_ev, tabla(df_ev, {"valor contratado": m0, "costo del evento": m0, "utilidad": m0, "margen %": pc}),
        hbar([(r.tipo, r.n) for r in d["tipos_evento"].itertuples()], ent, "var(--bl)"),
        f"Se ejecutaron {len(ev)} eventos por {cop(ev.valor.sum())} ({pc(100*ev.valor.sum()/(ING+ev.valor.sum()))} de los ingresos totales) con margen de {pc(100*ev.utilidad.sum()/ev.valor.sum())}, superior al margen neto del restaurante: son pocos, pero rentables. De los {len(d['tipos_evento'])} tipos del catálogo solo {int((d['tipos_evento'].n>0).sum())} se han usado.")

    # --- Diagnóstico
    q = d["calidad"].iloc[0]; tr = d["operativo"][d["operativo"].c.str.startswith("Transporte")].k.sum()
    diag = pd.DataFrame([
     ("Margen neto bajo", f"Margen neto {pc(100*UT/ING)}; gastos operativos = {pc(100*OP/ING)} de los ingresos.", "Controlar gastos fijos (nómina, arriendo) y subir ventas en horas valle para diluirlos."),
     ("Productos de bajo margen", f"{lo.n} deja solo {pc(lo.mg)} de margen bruto; {ca.sort_values('mg').iloc[0].c} es la categoría menos rentable ({pc(ca.mg.min())}).", "Revisar recetas y precios; empujar los productos de mayor margen."),
     ("Venta cruzada débil", f"Cerveza en {pc(ca.set_index('c').inc.get('Cerveza', 0))} y acompañantes en {pc(ca.set_index('c').inc.get('Acompañante', 0))} de las ventas.", "Combos almuerzo + bebida + acompañante y sugerencia en caja."),
     ("Horas y días valle", f"Las 3 horas más bajas suman {pc(bot3.pct.sum())} de las ventas; día más flojo: {DIAS[int(dd.loc[dd.ventas.idxmin(), 'd'])-1]}.", "Promociones y domicilios en franjas bajas; ajustar turnos del personal."),
     ("Dependencia de pocos clientes", f"{len(fr)} clientes generan {pc(fr.sh.sum())} de los ingresos.", "Programa de fidelización y captación de nuevos clientes."),
     ("Costo del domicilio", f"El transporte suma {cop(tr)} frente a {cop(dom.ingresos)} vendidos por domicilio ({pc(100*tr/dom.ingresos)}).", "Medir rentabilidad por pedido y definir un valor mínimo o costo de envío."),
     ("Eventos subaprovechados", f"Solo {len(ev)} eventos ejecutados, con margen {pc(100*ev.utilidad.sum()/ev.valor.sum())}.", "Promocionar paquetes para cumpleaños, bautizos y corporativos."),
     ("Calidad de datos", f"Clientes sin compras: {int(q.cli_sin_compras)}; ventas descuadradas: {int(q.ventas_descuadradas)}; productos sin ventas: {int(q.prod_sin_ventas)}. 'cliente_frecuente' y precios históricos no se almacenan.", "Registrar costos reales, historial de precios y la fecha de cada pedido; validar totales al insertar."),
    ], columns=["Hallazgo", "Evidencia", "Acción propuesta"])
    tt = d["tablas"].set_index("t").n
    ORI = {"cliente": ("Original", "Clientes que compran o reservan"), "empleado": ("Original", "Personal que registra ventas"), "producto": ("Mixto", "Menú: 6 originales + 10 nuevos (gaseosas, cervezas, acompañantes)"),
           "domicilio": ("Original", "Entregas de ventas a domicilio"), "tipo_evento": ("Simulado", "Catálogo de tipos de evento"), "evento": ("Mixto", "Eventos ejecutados (máx. 3)"),
           "venta": ("Original", "Cabecera de la venta"), "detalle_venta": ("Mixto", "Líneas de la venta"), "costo": ("Simulado", "Costos de producción, operativos y de evento")}
    df_tab = pd.DataFrame([(t, tt[t], *ORI[t]) for t in ORI], columns=["tabla", "registros", "origen", "descripción"])
    mer = (BASE / "docs" / "modelo_relacional.mermaid").read_text(encoding="utf-8").split("---", 2)[-1].strip()
    cfg = d["kpi"].iloc[0]
    body = f'''<header><p>Business Intelligence 801SIS · Ingeniería de Sistemas · Universidad de Cundinamarca · Ing. Ivon Forero</p>
<h1>Análisis descriptivo del proyecto de aula: Restaurante El Buen Sazón</h1>
<p>Camilo Soler · Sebastián Valencia · Juan Acevedo · Wilson Cristancho · Santiago Mahecha</p></header>
<nav><a href="#s1">1. Modelo de negocio</a><a href="#s2">2. Proceso foco</a><a href="#s3">3. Conjunto de datos</a><a href="#qsql">26 consultas</a><a href="#s4">4. Indicadores (KPIs)</a><a href="#s5">5. Diagnóstico</a></nav>
<main>
<section id="s1"><h2>1. Contextualización del modelo de negocio</h2>
<p><b>Nombre y sector.</b> Restaurante El Buen Sazón, negocio del sector gastronómico (servicio de alimentos) ubicado en Facatativá, Cundinamarca. Ofrece desayunos y almuerzos de comida casera, bebidas y acompañantes, con venta en el local y a domicilio, y reserva de eventos.</p>
<p><b>Procesos considerados en el análisis.</b></p><ul><li><b>Venta:</b> un empleado registra la venta de un cliente (local o domicilio) y sus productos.</li><li><b>Domicilio:</b> pedidos con dirección y teléfono de entrega.</li><li><b>Catálogo y costos:</b> productos con precio, costos de producción y gastos operativos mensuales.</li><li><b>Eventos:</b> reservas de celebraciones (cumpleaños, bautizos, corporativos) por cliente.</li></ul></section>
<section id="s2"><h2>2. Identificación del proceso foco de estudio</h2>
<p><b>Nombre del proceso.</b> Gestión de ventas y rentabilidad (registro de ventas en local y a domicilio).</p>
<p><b>Objetivo.</b> Registrar cada venta con su detalle de forma correcta y completa, para conocer qué se vende, cuándo, a quién y con qué margen, y así maximizar ingresos y utilidad.</p>
<p><b>Justificación.</b> Es el proceso que genera los ingresos y concentra los costos. El análisis muestra un margen neto de apenas {pc(100*UT/ING)}, ventas concentradas en pocas horas y clientes, y baja venta cruzada: mejorar este proceso tiene el mayor efecto sobre el negocio.</p></section>
<section id="s3"><h2>3. Conjunto de datos</h2>
<h3>Diagrama entidad-relación (modelo relacional ajustado)</h3>
<p>Ajustes de la revisión en clase: se extrajo la entidad <code>tipo_evento</code> de <code>evento</code>, se agregó la tabla <code>costo</code> (producción, operativos y eventos) y se amplió <code>producto</code> con gaseosas, cervezas y acompañantes.</p>
<pre class="mermaid">{mer}</pre>
<h3>Base de datos (PostgreSQL, esquema <code>ventas</code>)</h3>
{tabla(df_tab, {"registros": ent})}
<p class="nt"><b>Nota sobre los datos.</b> Clientes, empleados, domicilios y ventas provienen del conjunto de datos original del proyecto. Los costos, los tipos de evento, el evento 3, los valores de los eventos y los productos nuevos (con sus líneas de venta) fueron simulados para completar el análisis de rentabilidad; por eso las conclusiones sobre costos son ilustrativas. Se validaron 26 consultas SQL (resumen de ventas, por canal, día, mes y hora, clientes, empleados, productos, eventos, costos y rentabilidad).</p>
<h3>Conexión de la base de datos con Python</h3>
<p>El gestor es PostgreSQL, por eso se usa <b>SQLAlchemy</b> con el controlador <b>psycopg2</b> y <b>pandas</b>. El proceso técnico es: (1) crear el <i>engine</i> con las credenciales de la variable de entorno <code>DATABASE_URL</code> (cargada con <code>python-dotenv</code>); (2) ejecutar cada consulta SQL con <code>pd.read_sql</code>, que devuelve un DataFrame; (3) transformar con pandas (<code>groupby</code>, <code>merge</code>, <code>describe</code>) para calcular los estadísticos; (4) presentar tablas, gráficos y conclusiones. Se ejecutaron {len(QUERIES)} consultas del informe y {len(EXTRA)} adicionales del blog, además de las 26 consultas validadas de la sustentación (se muestran completas más abajo), para construir 10 DataFrames.</p>
{src_con}{src_ext}
<p class="nt">Ejemplo mínimo de conexión y primera consulta:</p>
{src_snip}
<h3 id="qsql">Consultas SQL validadas en la sustentación (26) y su resultado</h3>
<p>Las 26 consultas de <code>database/03_consultas.sql</code> se ejecutan una a una contra Supabase; cada bloque muestra el código fuente y, debajo, el DataFrame resultante (primeras 12 filas, con el total de filas y el tiempo de ejecución).</p>
{qhtml}</section>
<section id="s4"><h2>4. Análisis de indicadores (KPIs)</h2>
<p>Periodo: {cfg.desde} a {cfg.hasta} · {ent(k.ventas)} ventas · {cop(ING)} en ingresos · ticket promedio {m0(k.ticket_prom)} · {int(k.clientes)} clientes activos.</p>
{t1}{t2}{t3}{t4}{t5}{t6}{t7}{t8}{t9}{t10}</section>
<section id="s5"><h2>5. Diagnóstico de fallos y acciones por mejorar</h2>
{tabla(diag)}
<p class="cn"><b>Conclusión general.</b> El restaurante tiene una demanda estable y un buen volumen de ventas, pero su rentabilidad es ajustada ({pc(100*UT/ING)} de margen neto). Las mayores oportunidades están en aumentar el ticket con venta cruzada, aprovechar las horas valle, proteger a los clientes más fiables y registrar costos reales para decidir con datos.</p></section></main>
<footer>Datos extraídos de PostgreSQL con Python (pandas + SQLAlchemy). Proyecto de aula · Octubre de 2026.</footer>'''
    out_root = BASE / "blog_el_buen_sazon.html"
    out_app = BASE / "app" / "static" / "blog.html"
    out_app.parent.mkdir(exist_ok=True)
    doc = HEAD + body + SCRIPT + "</body></html>"
    for ruta in (out_root, out_app):
        ruta.write_text(doc, encoding="utf-8")
        print(f"{ruta.relative_to(BASE)}  {len(doc) // 1024} KB")

SCRIPT = '''<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
mermaid.initialize({startOnLoad:true, theme:"neutral", securityLevel:"loose"});
</script>
'''
HEAD = '''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Blog · Análisis descriptivo · Restaurante El Buen Sazón</title><style>
:root{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);--bg:#faf7f4;--cd:#fff;--tx:#2b2523;--mu:#6b625d;--ac:#c4581b;--bl:#118dff;--ok:#12a579;--bd:#e6dfd9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1c1917;--cd:#292524;--tx:#f5f0ec;--mu:#a8a09a;--bd:#3d3733}}
:root[data-theme="dark"]{--bg:#1c1917;--cd:#292524;--tx:#f5f0ec;--mu:#a8a09a;--bd:#3d3733}
html{scroll-padding-top:env(safe-area-inset-top,0px)}body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.65 Georgia,serif}
header{background:linear-gradient(120deg,#7a2e0c,#c4581b);color:#fff;padding:28px 18px;text-align:center}header h1{margin:8px 0;font-size:28px}header p{margin:2px 0;font:14px sans-serif;opacity:.92}
nav{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;padding:10px;background:var(--cd);border-bottom:1px solid var(--bd);position:sticky;top:env(safe-area-inset-top,0px);z-index:5}nav a{font:13px sans-serif;color:var(--ac);text-decoration:none;padding:3px 9px;border:1px solid var(--bd);border-radius:14px}
main{max-width:860px;margin:0 auto;padding:6px 16px 30px}h2{color:var(--ac);border-bottom:2px solid var(--bd);padding-bottom:4px;margin-top:34px}h3{margin:20px 0 6px}
article{background:var(--cd);border:1px solid var(--bd);border-radius:8px;padding:6px 14px 12px;margin:16px 0}.df{font:12px sans-serif;color:var(--mu);margin:0 0 6px}code{background:var(--bd);padding:1px 5px;border-radius:3px;font-size:.88em}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font:12.5px sans-serif}th,td{padding:5px 7px;border-bottom:1px solid var(--bd);text-align:right;white-space:nowrap}th{background:var(--bd)}th:first-child,td:first-child{text-align:left}td:last-child:not(:only-child){white-space:normal}
.ch{margin:12px 0}.hb div{display:grid;grid-template-columns:minmax(90px,32%) 1fr auto;gap:8px;align-items:center;font:12px sans-serif;margin:3px 0}.hb span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hb i{background:var(--bd);height:12px;border-radius:3px;display:block}.hb b{display:block;height:100%;border-radius:3px}.hb em{font-style:normal;font-weight:600}
.vb{display:flex;gap:3px;align-items:flex-end;height:170px}.vb div{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;font:9px sans-serif;min-width:0}.vb i{flex:1;width:100%;display:flex;align-items:flex-end}.vb b{display:block;width:100%;background:var(--ac);border-radius:3px 3px 0 0;min-height:2px}.vb em{font-style:normal;font-weight:600}
.cn{background:var(--bd);border-left:4px solid var(--ac);padding:8px 12px;border-radius:4px;font-size:15px}.nt{font-size:14px;color:var(--mu)}
.carbon{margin:10px 0 6px;border-radius:8px;overflow:hidden;box-shadow:0 3px 14px rgba(0,0,0,.28);background:#282c34}
.cb-top{display:flex;align-items:center;gap:8px;padding:9px 12px;background:#21252b}
.cb-dots i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px}
.cb-dots i:nth-child(1){background:#ff5f56}.cb-dots i:nth-child(2){background:#ffbd2e}.cb-dots i:nth-child(3){background:#27c93f}
.cb-file{flex:1;text-align:center;font:12px/1.2 ui-monospace,Consolas,monospace;color:#9da5b4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cb-lang{font:10px/1.2 ui-monospace,Consolas,monospace;color:#5f6672;letter-spacing:1.5px}
pre.cb-code{margin:0;background:#282c34;color:#d6deeb;padding:12px 10px;font:12.5px/1.55 ui-monospace,Consolas,"Cascadia Mono",monospace;overflow-x:auto}
pre.cb-code code{background:none;padding:0;color:inherit;font-size:inherit}
.cb-code .ln{display:inline-block;width:2.4em;padding-right:.9em;text-align:right;color:#4b5263;user-select:none}
.t-c{color:#5c6370;font-style:italic}.t-s{color:#98c379}.t-k{color:#c678dd}.t-n{color:#d19a66}
.q{background:var(--cd);border:1px solid var(--bd);border-radius:8px;padding:2px 14px 12px;margin:14px 0}
.q h4{margin:14px 0 8px;font-size:15px}
.gq{margin:28px 0 4px;padding:7px 10px;background:var(--bd);border-left:4px solid var(--ac);border-radius:4px;font-size:16px}
pre{background:#1e1e1e;color:#e6e6e6;padding:12px;border-radius:6px;overflow-x:auto;font-size:12.5px;line-height:1.45}pre.mermaid{background:var(--cd);color:var(--tx);text-align:center}
footer{text-align:center;font:12px sans-serif;color:var(--mu);padding:16px}
</style></head><body>'''
if __name__ == "__main__":
    main()
