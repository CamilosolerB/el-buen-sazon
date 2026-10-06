"""Sistema de información - Restaurante El Buen Sazón (FastAPI).
Lee la base de datos en cada consulta (con caché corta), calcula el análisis con pandas
y sirve el informe web. Ejecutar: uvicorn app.main:app --reload"""
import os, json, time, threading
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from app.analisis import conectar, extraer, construir, PLANTILLA

app = FastAPI(title="El Buen Sazón · Sistema de información", version="1.0")
TTL = int(os.getenv("CACHE_SEGUNDOS", "60"))          # segundos antes de volver a consultar la BD
_lock, _motor, _cache = threading.Lock(), None, {"t": 0.0, "datos": None, "hora": ""}
BARRA = ('<div style="background:#fff3e8;color:#7a2e0c;font:12px sans-serif;padding:6px 14px;text-align:right">'
         'Datos en vivo desde Supabase · actualizado {hora} · <a href="/?refrescar=1">Actualizar ahora</a> · <a href="/docs">API</a></div>')

def motor():
    global _motor
    if _motor is None: _motor = conectar()
    return _motor

def obtener(forzar=False):
    with _lock:
        if forzar or _cache["datos"] is None or time.time() - _cache["t"] > TTL:
            _cache.update(datos=construir(extraer(motor())), t=time.time(),
                          hora=datetime.now(ZoneInfo("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S"))
        return _cache["datos"], _cache["hora"]

@app.get("/", response_class=HTMLResponse)
def informe(refrescar: int = 0):
    """Informe interactivo (KPIs, productos, clientes, rentabilidad y eventos)."""
    try: datos, hora = obtener(bool(refrescar))
    except Exception as e:
        return HTMLResponse(f"<h2>No se pudo consultar la base de datos</h2><p>{type(e).__name__}. Revise DATABASE_URL.</p>", 503)
    html = PLANTILLA.replace("__DATA__", json.dumps(datos, ensure_ascii=False, default=float))
    return html.replace("<main>", BARRA.format(hora=hora) + "<main>", 1)

@app.get("/api/resumen")
def resumen():
    """KPIs globales en JSON."""
    d, hora = obtener()
    ing, ven = sum(r["i"] for r in d["mc"]), sum(r["v"] for r in d["mc"])
    cp, op = sum(r["k"] for r in d["cp"]), sum(r["a"] for r in d["op"])
    return {"actualizado": hora, "periodo": d["per"], "ventas": ven, "ingresos": ing, "ticket_promedio": round(ing / ven, 2),
            "costo_produccion": cp, "gastos_operativos": op, "utilidad": ing - cp - op, "margen_neto_pct": round(100 * (ing - cp - op) / ing, 2)}

@app.get("/api/ventas-mensuales")
def ventas_mensuales():
    """Ventas e ingresos por mes."""
    d, _ = obtener(); a = {}
    for r in d["mc"]:
        x = a.setdefault(r["m"], {"mes": r["m"], "ventas": 0, "ingresos": 0}); x["ventas"] += r["v"]; x["ingresos"] += r["i"]
    return list(a.values())

@app.get("/health")
def health():
    try:
        with motor().connect() as cn: cn.execute(text("SELECT 1"))
        return {"estado": "ok"}
    except Exception: return JSONResponse({"estado": "sin conexión a la base de datos"}, 503)
