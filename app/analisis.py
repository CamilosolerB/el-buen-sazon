#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análisis descriptivo - Restaurante El Buen Sazón
================================================
Se conecta a PostgreSQL (esquema `ventas`), ejecuta las consultas documentadas
más abajo, calcula los indicadores con pandas y genera el informe HTML
(`informe_el_buen_sazon.html`) con estilo de reporte Power BI.

Requisitos:   pip install pandas sqlalchemy psycopg2-binary
Conexión:     DATABASE_URL (Supabase) o variables de entorno PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
              (por defecto: localhost:5432 / el_buen_sabor / postgres)
Ejecución:    PGPASSWORD=su_clave python analisis_descriptivo.py [-o salida.html]
"""
import os, re, json, argparse
from urllib.parse import quote_plus
import pandas as pd
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# 1. CONSULTAS SQL (cada una alimenta una sección del informe)
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
# 2. CONEXIÓN Y EXTRACCIÓN
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

# ---------------------------------------------------------------------------
# 3. ANÁLISIS DESCRIPTIVO (hallazgos del periodo completo)
# ---------------------------------------------------------------------------
ent = lambda n: f"{int(n):,}".replace(",", ".")
cop = lambda n: f"${n/1e6:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".") if abs(n) >= 1e6 else f"${n:,.0f}".replace(",", ".")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

def hallazgos(d):
    k = d["kpi"].iloc[0]; out = []
    mc = d["mes_canal"]; ing = mc.i.sum()
    mes = mc.groupby("m").i.sum(); completos = mes.iloc[1:-1]          # primer y último mes son parciales
    top = completos.idxmax(); low = completos.idxmin()
    out.append(f"<b>Ventas.</b> En {k.desde} a {k.hasta} se registraron <b>{ent(k.ventas)}</b> ventas por <b>{cop(ing)}</b> "
               f"(ticket promedio {cop(k.ticket_prom)}, mediana {cop(k.ticket_mediana)}, 10 % de los tickets supera {cop(k.ticket_p90)}). "
               f"Entre los meses completos, {MESES[int(top[5:])]} fue el mejor ({cop(completos.max())}) y {MESES[int(low[5:])]} el más bajo ({cop(completos.min())}).")
    c = mc.groupby("canal").agg(v=("v", "sum"), i=("i", "sum")); c["t"] = c.i / c.v
    out.append("<b>Canales.</b> " + "; ".join(f"{n}: {100*r.i/ing:.0f} % de los ingresos, ticket {cop(r.t)}" for n, r in c.iterrows()) + ".")
    h = d["hora"].groupby("h").agg(v=("v", "sum")); dd = d["dia"].groupby("d").agg(v=("v", "sum"), i=("i", "sum"))
    out.append(f"<b>Cuándo se vende.</b> La hora pico es las {int(h.v.idxmax())}:00 ({ent(h.v.max())} ventas) y el día más fuerte es el {DIAS[int(dd.v.idxmax())-1]}; "
               f"el más flojo es el {DIAS[int(dd.v.idxmin())-1]}.")
    p = d["producto"].merge(d["costo_prod"], left_on=["m", "id_producto"], right_on=["m", "id_producto"], how="left").fillna({"k": 0})
    pr = p.groupby(["n", "c"]).agg(u=("u", "sum"), i=("i", "sum"), k=("k", "sum")).reset_index(); pr["mg"] = 100 * (pr.i - pr.k) / pr.i
    ca = pr.groupby("c").agg(i=("i", "sum"), k=("k", "sum")); ca["mg"] = 100 * (ca.i - ca.k) / ca.i
    l = pr.sort_values("i").iloc[-1]; mm = pr.sort_values("mg").iloc[-1]
    out.append(f"<b>Productos.</b> El líder en ingresos es <b>{l.n}</b> ({cop(l.i)}, {100*l.i/pr.i.sum():.0f} % del total). "
               f"El de mayor margen es <b>{mm.n}</b> ({mm.mg:.0f} %). Por categoría, {ca.mg.idxmax()} es la más rentable ({ca.mg.max():.0f} %) y {ca.mg.idxmin()} la menos ({ca.mg.min():.0f} %).")
    cv = d["categoria_venta"].groupby("c").v.sum(); tv = mc.v.sum()
    out.append(f"<b>Venta cruzada.</b> {100*cv.get('Gaseosa',0)/tv:.0f} % de las ventas incluye gaseosa, {100*cv.get('Acompañante',0)/tv:.0f} % un acompañante y {str(round(100*cv.get('Cerveza',0)/tv,1)).replace('.',',')} % cerveza.")
    cl = d["cliente"].groupby("n").agg(v=("v", "sum"), i=("i", "sum")).sort_values("i", ascending=False)
    out.append(f"<b>Clientes.</b> {int(k.clientes)} clientes compraron; los 12 principales concentran {100*cl.i.head(12).sum()/cl.i.sum():.0f} % de los ingresos "
               f"y el mayor ({cl.index[0]}) aporta {cop(cl.i.iloc[0])}.")
    em = d["empleado"].groupby("n").i.sum().sort_values(ascending=False)
    out.append(f"<b>Equipo.</b> {em.index[0]} gestionó el mayor valor de ventas ({cop(em.iloc[0])}); {em.index[-1]} el menor ({cop(em.iloc[-1])}).")
    cpv, ops = d["costo_prod"].k.sum(), d["operativo"].k.sum(); ut = ing - cpv - ops
    out.append(f"<b>Rentabilidad.</b> Costo de producción {cop(cpv)} ({100*cpv/ing:.0f} % de los ingresos) y gastos operativos {cop(ops)}: "
               f"utilidad de <b>{cop(ut)}</b>, margen neto de <b>{str(round(100*ut/ing,1)).replace('.',',')} %</b>.")
    e = d["eventos"]; e["u"] = e.valor - e.costo; b = e.sort_values("u").iloc[-1]
    out.append(f"<b>Eventos.</b> Se ejecutaron {len(e)} eventos por {cop(e.valor.sum())} con utilidad de {cop(e.u.sum())} "
               f"({100*e.u.sum()/e.valor.sum():.0f} %); el más rentable fue el de tipo {b.tipo} ({cop(b.u)}).")
    return out

# ---------------------------------------------------------------------------
# 4. INFORME HTML (plantilla estilo Power BI, datos embebidos)
# ---------------------------------------------------------------------------
PLANTILLA = r'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>El Buen Sazón · Informe de análisis descriptivo</title>
<style>
:root{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);--bg:#f3f2f1;--cd:#fff;--tx:#252423;--mu:#605e5c;--ac:#c4581b;--bl:#118dff;--ok:#12a579;--bd:#e1dfdd;--rd:#d64550}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1b1a19;--cd:#292827;--tx:#f3f2f1;--mu:#a19f9d;--bd:#3b3a39}}
:root[data-theme="dark"]{--bg:#1b1a19;--cd:#292827;--tx:#f3f2f1;--mu:#a19f9d;--bd:#3b3a39}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.5 "Segoe UI",system-ui,sans-serif}
header{background:linear-gradient(120deg,#7a2e0c,#c4581b);color:#fff;padding:22px 16px}
header h1{margin:0;font-size:24px}header p{margin:4px 0 0;opacity:.9}
main{max-width:1100px;margin:0 auto;padding:12px 12px 40px}
#sl{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);padding:8px 0;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
#sl b{font-size:12px;color:var(--mu);margin-right:4px}
.chip{border:1px solid var(--bd);background:var(--cd);color:var(--tx);border-radius:14px;padding:3px 11px;cursor:pointer;font:inherit;font-size:12px}
.chip.on{background:var(--ac);border-color:var(--ac);color:#fff}
h2{font-size:17px;margin:26px 0 8px;border-left:4px solid var(--ac);padding-left:8px}
.g{display:grid;gap:10px}.k{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.c2{grid-template-columns:repeat(auto-fit,minmax(310px,1fr))}
.cd{background:var(--cd);border:1px solid var(--bd);border-radius:6px;padding:12px;min-width:0}
.cd h3{margin:0 0 8px;font-size:13px;color:var(--mu);font-weight:600}
.kp{font-size:24px;font-weight:700}.kp small{display:block;font-size:11px;font-weight:400;color:var(--mu)}
.hb{display:grid;grid-template-columns:minmax(80px,38%) 1fr auto;gap:8px;align-items:center;margin:4px 0;font-size:12px}
.hb .l{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tr{background:var(--bd);height:12px;border-radius:3px}.tr i{display:block;height:100%;border-radius:3px}
.cols{display:flex;gap:4px;align-items:flex-end;height:170px}.col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;font-size:10px;min-width:0;cursor:default}
.col b{font-weight:600;font-size:9px;white-space:nowrap}.bar{width:100%;flex:1;display:flex;align-items:flex-end}.bar i{width:100%;background:var(--ac);border-radius:3px 3px 0 0;min-height:2px}
.col.off .bar i{background:var(--bd)}.col[data-k]{cursor:pointer}
.ins li{margin:6px 0}table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:5px 6px;border-bottom:1px solid var(--bd);text-align:right}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
.mu{color:var(--mu);font-size:12px}
</style></head><body>
<header><h1>🍽️ Restaurante El Buen Sazón</h1><p>Informe de análisis descriptivo de ventas, productos, clientes, costos y eventos · <span id="per"></span></p></header>
<main>
<div id="sl"></div>
<div class="g k" id="kp"></div>

<h2>Ventas en el tiempo</h2>
<div class="g c2">
<div class="cd"><h3>Ingresos por mes (clic para filtrar)</h3><div class="cols" id="cm"></div></div>
<div class="cd"><h3>Canal de venta</h3><div id="cc"></div></div>
<div class="cd"><h3>Ventas por hora del día</h3><div class="cols" id="ch"></div></div>
<div class="cd"><h3>Ventas por día de la semana</h3><div class="cols" id="cd"></div></div>
</div>

<h2>Hallazgos del periodo completo</h2>
<div class="cd"><ul class="ins" id="ins"></ul></div>

<h2>Productos</h2>
<div class="g c2">
<div class="cd"><h3>Ingresos por producto</h3><div id="pi"></div></div>
<div class="cd"><h3>Margen bruto por producto (%)</h3><div id="pm"></div></div>
<div class="cd"><h3>% de ventas que incluyen cada categoría</h3><div id="pa"></div></div>
</div>

<h2>Clientes y equipo</h2>
<div class="g c2">
<div class="cd"><h3>Top 10 clientes por ingresos</h3><div id="kc"></div></div>
<div class="cd"><h3>Ingresos gestionados por empleado</h3><div id="ke"></div></div>
</div>

<h2>Rentabilidad</h2>
<div class="g c2">
<div class="cd"><h3>Resultado del periodo seleccionado</h3><div id="rp"></div></div>
<div class="cd"><h3>Gastos operativos por concepto</h3><div id="ro"></div></div>
</div>

<h2>Eventos</h2>
<div class="g c2">
<div class="cd"><h3>Eventos ejecutados</h3><table id="ev"></table></div>
<div class="cd"><h3>Tipos de evento (eventos ejecutados)</h3><div id="te"></div></div>
</div>
<p class="mu">Datos leídos de PostgreSQL (esquema ventas) con las consultas de analisis_descriptivo.py. Margen bruto = ingresos − costo de producción; utilidad = margen bruto − gastos operativos. Los eventos se analizan aparte del restaurante.</p>
</main>
<script>
const D=__DATA__,$=s=>document.querySelector(s),MS=D.meses;let sel=new Set(MS);
const MN=["","ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"],DN=["","Lun","Mar","Mié","Jue","Vie","Sáb","Dom"];
const num=n=>Math.round(n).toLocaleString("es-CO"),cop=n=>Math.abs(n)>=1e6?"$"+(n/1e6).toFixed(1).replace(".",",")+" M":"$"+num(n),pc=n=>n.toFixed(1).replace(".",",")+" %";
const F=a=>a.filter(r=>sel.has(r.m)),S=(a,k)=>a.reduce((s,r)=>s+r[k],0);
function G(a,key,vals){const m=new Map();for(const r of a){let o=m.get(r[key]);if(!o){o={k:r[key]};vals.forEach(v=>o[v]=0);m.set(r[key],o)}vals.forEach(v=>o[v]+=r[v]);for(const x in r)if(!(x in o))o[x]=r[x]}return[...m.values()]}
function hb(id,it,fmt){const mx=Math.max(...it.map(i=>Math.abs(i.v)),1);$(id).innerHTML=it.map(i=>`<div class="hb"><span class="l" title="${i.l}">${i.l}</span><div class="tr"><i style="width:${Math.abs(i.v)/mx*100}%;background:${i.c||"var(--ac)"}"></i></div><b>${fmt(i.v)}</b></div>`).join("")||'<p class="mu">Sin datos</p>'}
function cl(id,it,fmt){const mx=Math.max(...it.map(i=>i.v),1);$(id).innerHTML=it.map(i=>`<div class="col${i.off?" off":""}"${i.k?` data-k="${i.k}"`:""}><b>${fmt(i.v)}</b><div class="bar"><i style="height:${i.v/mx*100}%"></i></div><span>${i.l}</span></div>`).join("")}
const CC={Desayuno:"#e8a33d",Almuerzo:"#c4581b",Gaseosa:"#118dff",Cerveza:"#8a5a00",Acompañante:"#12a579"};
function draw(){
 const mc=F(D.mc),ing=S(mc,"i"),vt=S(mc,"v"),cp=S(F(D.cp),"k"),op=S(F(D.op),"a"),ut=ing-cp-op;
 $("#sl").innerHTML="<b>Mes:</b>"+MS.map(m=>`<button class="chip${sel.has(m)?" on":""}" data-m="${m}">${MN[+m.slice(5)]} ${m.slice(2,4)}</button>`).join("")+'<button class="chip" data-m="*">Todos</button>';
 const K=[["Ingresos",cop(ing)],["Ventas",num(vt)],["Ticket promedio",cop(vt?ing/vt:0)],["Costo de producción",cop(cp)],["Gastos operativos",cop(op)],["Utilidad",cop(ut)],["Margen neto",pc(ing?100*ut/ing:0)]];
 $("#kp").innerHTML=K.map(([a,b])=>`<div class="cd"><div class="kp">${b}<small>${a}</small></div></div>`).join("");
 const pm=G(D.mc,"m",["i"]);cl("#cm",pm.map(r=>({l:MN[+r.k.slice(5)],v:r.i,k:r.k,off:!sel.has(r.k)})),cop);
 const ca=G(mc,"canal",["v","i"]);hb("#cc",ca.map(r=>({l:`${r.k} · ${num(r.v)} ventas · ticket ${cop(r.i/r.v)}`,v:r.i,c:r.k=="Local"?"var(--ac)":"var(--bl)"})),cop);
 cl("#ch",G(F(D.h),"h",["v"]).sort((a,b)=>a.k-b.k).map(r=>({l:r.k+"h",v:r.v})),num);
 cl("#cd",G(F(D.d),"d",["v"]).sort((a,b)=>a.k-b.k).map(r=>({l:DN[r.k],v:r.v})),num);
 const cst={};D.cp.filter(r=>sel.has(r.m)).forEach(r=>cst[r.id]=(cst[r.id]||0)+r.k);
 const pr=G(F(D.p),"id",["u","i"]).map(r=>({...r,k:cst[r.k]||0}));
 hb("#pi",pr.sort((a,b)=>b.i-a.i).map(r=>({l:r.n,v:r.i,c:CC[r.c]})),cop);
 hb("#pm",pr.filter(r=>r.i).map(r=>({l:r.n,v:100*(r.i-r.k)/r.i,c:CC[r.c]})).sort((a,b)=>b.v-a.v),pc);
 const ac=G(F(D.cv),"c",["v"]);hb("#pa",ac.map(r=>({l:r.k,v:100*r.v/(vt||1),c:CC[r.k]})).sort((a,b)=>b.v-a.v),pc);
 hb("#kc",G(F(D.cli),"n",["v","i"]).sort((a,b)=>b.i-a.i).slice(0,10).map(r=>({l:r.k,v:r.i})),cop);
 hb("#ke",G(F(D.emp),"n",["v","i"]).sort((a,b)=>b.i-a.i).map(r=>({l:`${r.k} (${r.g})`,v:r.i,c:"var(--bl)"})),cop);
 hb("#rp",[{l:"Ingresos",v:ing,c:"var(--bl)"},{l:"Costo de producción",v:cp,c:"var(--rd)"},{l:"Gastos operativos",v:op,c:"var(--rd)"},{l:"Utilidad",v:ut,c:"var(--ok)"}],cop);
 hb("#ro",G(F(D.op),"c",["a"]).sort((a,b)=>b.a-a.a).map(r=>({l:r.k,v:r.a,c:"#8a5a00"})),cop)
}
document.addEventListener("click",e=>{const m=e.target.closest("[data-m],[data-k]");if(!m)return;const k=m.dataset.m||m.dataset.k;
 if(k=="*")sel=new Set(MS);else if(sel.has(k)){if(sel.size>1)sel.delete(k)}else sel.add(k);draw()});
$("#per").textContent=D.per;$("#ins").innerHTML=D.ins.map(t=>`<li>${t}</li>`).join("");
$("#ev").innerHTML="<tr><th>Tipo</th><th>Fecha</th><th>Valor</th><th>Costo</th><th>Utilidad</th></tr>"+D.ev.map(r=>`<tr><td>${r.tipo}</td><td>${r.fecha}</td><td>${cop(r.valor)}</td><td>${cop(r.costo)}</td><td>${cop(r.valor-r.costo)} (${pc(100*(r.valor-r.costo)/r.valor)})</td></tr>`).join("");
hb("#te",D.te.map(r=>({l:r.tipo,v:r.n,c:"var(--bl)"})),num);
draw();
</script></body></html>'''

def construir(d):
    """Arma el JSON que consume la plantilla (claves cortas para mantener el HTML liviano)."""
    k = d["kpi"].iloc[0]
    return dict(
        meses=sorted(d["mes_canal"].m.unique()), per=f"{k.desde} a {k.hasta}", ins=hallazgos(d),
        mc=rows(d["mes_canal"]), h=rows(d["hora"]), d=rows(d["dia"]),
        p=rows(d["producto"].rename(columns={"id_producto": "id"})),
        cp=rows(d["costo_prod"].rename(columns={"id_producto": "id"})),
        op=rows(d["operativo"].rename(columns={"k": "a"})),
        cv=rows(d["categoria_venta"]), cli=rows(d["cliente"]), emp=rows(d["empleado"]),
        ev=rows(d["eventos"]), te=rows(d["tipos_evento"]))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--salida", default="informe_el_buen_sazon.html")
    a = ap.parse_args()
    print("Conectando a PostgreSQL y ejecutando consultas...")
    d = extraer(conectar())
    html = PLANTILLA.replace("__DATA__", json.dumps(construir(d), ensure_ascii=False, default=float))
    with open(a.salida, "w", encoding="utf-8") as f: f.write(html)
    print(f"Informe generado: {a.salida} ({len(html)/1024:.0f} KB)")
    for t in hallazgos(d): print(" -", t.replace("<b>", "").replace("</b>", ""))

if __name__ == "__main__":
    main()
