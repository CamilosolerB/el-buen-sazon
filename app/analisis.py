#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análisis descriptivo - Restaurante El Buen Sazón
================================================
Módulo de compatibilidad: la implementación vive en `app.db` (conexión y consultas
SQL) y `app/informe.py` (indicadores con pandas y render del HTML).

Conexión:  DATABASE_URL (Supabase) o variables PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
Ejecución: python -m app.analisis [-o salida.html]
"""
from app.db import QUERIES, conectar, extraer, rows
from app.informe import (DIAS, MESES, PLANTILLA_RUTA, construir, cop, ent,
                         hallazgos, main, plantilla, renderizar)

PLANTILLA = plantilla()   # HTML completo (antes venía embebido en este archivo)

__all__ = ["QUERIES", "conectar", "extraer", "rows", "DIAS", "MESES", "PLANTILLA",
           "PLANTILLA_RUTA", "construir", "cop", "ent", "hallazgos", "main",
           "plantilla", "renderizar"]

if __name__ == "__main__":
    main()
