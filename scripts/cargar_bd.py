"""Carga el esquema y los datos en Supabase/PostgreSQL (una sola transacción).
Uso:  python scripts/cargar_bd.py          (base vacía)
      python scripts/cargar_bd.py --reset  (borra el esquema ventas y recarga)"""
import os, sys, pathlib, psycopg2
from dotenv import load_dotenv
load_dotenv()
BASE = pathlib.Path(__file__).resolve().parent.parent / "database"
dsn = os.environ.get("DATABASE_URL") or sys.exit("Defina DATABASE_URL en el archivo .env")
cn = psycopg2.connect(dsn, **({"sslmode": "require"} if "supabase" in dsn else {})); cur = cn.cursor()
cur.execute("SELECT to_regclass('ventas.venta')"); existe = cur.fetchone()[0] is not None
if existe and "--reset" in sys.argv: cur.execute("DROP SCHEMA ventas CASCADE"); existe = False
if existe:
    cur.execute("SELECT COUNT(*) FROM ventas.venta")
    if cur.fetchone()[0]: sys.exit("La base ya tiene datos. Use --reset para recargar desde cero.")
if not existe: cur.execute((BASE / "01_schema.sql").read_text(encoding="utf-8")); print("Esquema ventas creado")
bloques = [b for b in (BASE / "02_datos.sql").read_text(encoding="utf-8").split("\n\n") if b.strip()]
for n, b in enumerate(bloques, 1):
    cur.execute(b)
    if n % 25 == 0 or n == len(bloques): print(f"  {n}/{len(bloques)} bloques cargados")
cn.commit()
for t in ("cliente", "empleado", "producto", "domicilio", "tipo_evento", "evento", "venta", "detalle_venta", "costo"):
    cur.execute(f"SELECT COUNT(*) FROM ventas.{t}"); print(f"  {t:14s} {cur.fetchone()[0]:>6}")
