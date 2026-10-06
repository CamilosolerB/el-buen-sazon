# Sistema de información · Restaurante El Buen Sazón

Aplicación web en Python (FastAPI + pandas + SQLAlchemy) que **consulta la base de datos en Supabase (PostgreSQL)** en cada visita y muestra el informe descriptivo con datos en vivo: ventas, productos, clientes, empleados, rentabilidad (costos) y eventos.

```
app/main.py            API y páginas web (FastAPI): informe en vivo, /blog y /mer.png
app/db.py              conexión a PostgreSQL (DATABASE_URL) y las 12 consultas SQL
app/informe.py         indicadores con pandas y render de la plantilla
app/analisis.py        módulo de compatibilidad (re-exporta db + informe)
app/templates/         informe.html (plantilla del informe, placeholders __DATA__ y __BARRA__)
app/static/blog.html   blog del proyecto de aula (se genera, se sirve en /blog)
app/static/mer.png     copia del diagrama E-R que sirve la aplicación al blog
database/              01_schema.sql · 02_datos.sql · 03_consultas.sql (26 consultas)
scripts/               cargar_bd.py (sube esquema y datos) · generar_blog.py (blog del curso)
scripts/consultas_pandas.py  las 26 consultas de la sustentación, reescritas en pandas y validadas
mer.png                diagrama entidad-relación en imagen (lo usa el blog en la sección 3)
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
Genera el blog (las 5 secciones de la normativa, los 10 KPIs y las **26 consultas analíticas
en Python + pandas**, con su código en estilo Carbon y su resultado) en tres archivos:
- `index.html` → el que se publica en **GitHub Pages** (ya está versionado).
- `blog_el_buen_sazon.html` → copia para subirla a Netlify, Vercel o Blogger.
- `app/static/blog.html` → se publica en la ruta **`/blog`** de esta aplicación.

Cada consulta se ejecuta en pandas (`scripts/consultas_pandas.py`) y se compara fila a fila con
la consulta SQL original de `database/03_consultas.sql`: el blog muestra el sello
*idéntico a la consulta SQL de la sustentación*. Solo la extracción usa SQL (`SELECT *` de las
9 tablas); todo el análisis del blog está en pandas. El diagrama E-R es la imagen `mer.png`,
así que la página no depende de ningún CDN.

## 4. Desplegar
- **Render:** New → Blueprint → seleccione este repo (usa `render.yaml`) y defina `DATABASE_URL`.
  La app publica `/` (datos en vivo) y `/blog`.
- **Railway / Fly.io / Cloud Run:** usan el `Dockerfile`; defina la variable `DATABASE_URL`.
- **Sitio estático (sin backend):** `index.html` ya es el sitio de Pages; para otro host suba `blog_el_buen_sazon.html` (junto con `mer.png`).

## Nota sobre los datos
Clientes, empleados, domicilios y ventas son los del proyecto. Los costos, los tipos de evento, los eventos y los productos nuevos (gaseosas, cervezas, acompañantes) con sus líneas de venta fueron **simulados**.
