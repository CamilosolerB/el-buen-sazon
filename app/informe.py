"""Análisis descriptivo y construcción del informe HTML.

Lee la base con `app.db`, calcula los indicadores con pandas y arma el JSON que
consume la plantilla `app/templates/informe.html`."""
import json, argparse
from pathlib import Path
from app.db import conectar, extraer, rows, QUERIES

# ---------------------------------------------------------------------------
# 1. ANÁLISIS DESCRIPTIVO (hallazgos del periodo completo)
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
# 2. INFORME HTML (plantilla externa, datos embebidos)
# ---------------------------------------------------------------------------
PLANTILLA_RUTA = Path(__file__).resolve().parent / "templates" / "informe.html"

def plantilla():
    """Lee la plantilla desde disco (cacheada: el archivo solo cambia al redeployar)."""
    if not hasattr(plantilla, "_html"):
        plantilla._html = PLANTILLA_RUTA.read_text(encoding="utf-8")
    return plantilla._html

def renderizar(datos, barra=""):
    """Sustituye __DATA__ (JSON del análisis) y __BARRA__ (barra de estado) en la plantilla."""
    return (plantilla()
            .replace("__DATA__", json.dumps(datos, ensure_ascii=False, default=float))
            .replace("__BARRA__", barra))

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
    html = renderizar(construir(d))
    with open(a.salida, "w", encoding="utf-8") as f: f.write(html)
    print(f"Informe generado: {a.salida} ({len(html)/1024:.0f} KB)")
    for t in hallazgos(d): print(" -", t.replace("<b>", "").replace("</b>", ""))

if __name__ == "__main__":
    main()
