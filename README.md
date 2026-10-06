# Sistema de información · Restaurante El Buen Sazón

Aplicación web en Python (FastAPI + pandas + SQLAlchemy) que **consulta la base de datos en Supabase (PostgreSQL)** en cada visita y muestra el informe descriptivo con datos en vivo: ventas, productos, clientes, empleados, rentabilidad (costos) y eventos.

```
app/main.py            API y páginas web (FastAPI): informe en vivo y /blog
app/db.py              conexión a PostgreSQL (DATABASE_URL) y las 12 consultas SQL
app/informe.py         indicadores con pandas y render de la plantilla
app/analisis.py        módulo de compatibilidad (re-exporta db + informe)
app/templates/         informe.html (plantilla del informe, placeholders __DATA__ y __BARRA__)
app/static/blog.html   blog del proyecto de aula (se genera, se sirve en /blog)
database/              01_schema.sql · 02_datos.sql · 03_consultas.sql (26 consultas)
scripts/               cargar_bd.py (sube esquema y datos) · generar_blog.py (blog del curso)
docs/                  modelo relacional / E-R (Mermaid) y diccionario de datos (Excel)
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
Páginas: `/` informe · `/blog` blog del proyecto · `/api/resumen` KPIs · `/api/ventas-mensuales` · `/docs` Swagger · `/health`.
Los datos se vuelven a leer de la base cada `CACHE_SEGUNDOS` (60 por defecto) o con el botón *Actualizar ahora*.

## 3. Blog del proyecto de aula
```bash
python scripts/generar_blog.py
```
Genera el blog (las 5 secciones de la normativa, los 10 KPIs y las **26 consultas validadas**
con su código en estilo Carbon y su resultado) en dos archivos:
- `blog_el_buen_sazon.html` → súbelo tal cual a **GitHub Pages, Netlify, Vercel o Blogger**
  (es HTML estático autocontenido; solo el diagrama E-R necesita internet para Mermaid).
- `app/static/blog.html` → se publica solo en la ruta **`/blog`** de esta aplicación.

## 4. Desplegar
- **Render:** New → Blueprint → seleccione este repo (usa `render.yaml`) y defina `DATABASE_URL`.
  La app publica `/` (datos en vivo) y `/blog`.
- **Railway / Fly.io / Cloud Run:** usan el `Dockerfile`; defina la variable `DATABASE_URL`.
- **Sitio estático (sin backend):** suba `blog_el_buen_sazon.html` a Pages/Netlify/Blogger.

## Nota sobre los datos
Clientes, empleados, domicilios y ventas son los del proyecto. Los costos, los tipos de evento, los eventos y los productos nuevos (gaseosas, cervezas, acompañantes) con sus líneas de venta fueron **simulados**.
