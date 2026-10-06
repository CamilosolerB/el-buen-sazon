# Sistema de información · Restaurante El Buen Sazón

Aplicación web en Python (FastAPI + pandas + SQLAlchemy) que **consulta la base de datos en Supabase (PostgreSQL)** en cada visita y muestra el informe descriptivo con datos en vivo: ventas, productos, clientes, empleados, rentabilidad (costos) y eventos.

```
app/main.py         API y página web (FastAPI)
app/analisis.py     consultas SQL documentadas + cálculo con pandas + plantilla del informe
database/           01_schema.sql · 02_datos.sql · 03_consultas.sql (26 consultas)
scripts/            cargar_bd.py (sube esquema y datos) · generar_blog.py (blog del curso)
docs/               modelo relacional / E-R (Mermaid) y diccionario de datos (Excel)
```

## 1. Base de datos en Supabase
1. Cree un proyecto en [supabase.com](https://supabase.com) (plan gratuito) y guarde la contraseña de la base de datos.
2. En **Connect** copie la URI del **Session pooler** (funciona en hosts sin IPv6) y péguela en `.env` (copie `.env.example`).
3. Cargue el esquema `ventas` y los 41.520 registros: `python scripts/cargar_bd.py` (use `--reset` para recargar).

## 2. Probar en local
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload                          # http://localhost:8000
```
Páginas: `/` informe · `/api/resumen` KPIs · `/api/ventas-mensuales` · `/docs` Swagger · `/health`.
Los datos se vuelven a leer de la base cada `CACHE_SEGUNDOS` (60 por defecto) o con el botón *Actualizar ahora*.

## 3. Desplegar
- **Render:** New → Blueprint → seleccione este repo (usa `render.yaml`) y defina `DATABASE_URL`.
- **Railway / Fly.io / Cloud Run:** usan el `Dockerfile`; defina la variable `DATABASE_URL`.

## Nota sobre los datos
Clientes, empleados, domicilios y ventas son los del proyecto. Los costos, los tipos de evento, los eventos y los productos nuevos (gaseosas, cervezas, acompañantes) con sus líneas de venta fueron **simulados**.
