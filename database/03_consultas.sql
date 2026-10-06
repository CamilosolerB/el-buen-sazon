-- 26 consultas (v2) para el caso de estudio: Restaurante El Buen Sazón
-- Esquema: ventas (según el modelo relacional del documento)
-- Ajuste realizado: las consultas 13 y 16 usaban el atributo cliente_frecuente,
-- que no existe en la tabla CLIENTE del modelo; ahora se deriva de las ventas.
-- v2: la consulta 20 usa tipo_evento (el tipo dejó de ser texto en evento) y se
-- agregan las consultas 21 a 26 sobre tipos de evento, costos y rentabilidad.

-- 1. Resumen general de ventas
SELECT COUNT(*) AS cantidad_ventas,
       SUM(total_venta) AS ingresos_totales,
       AVG(total_venta) AS ticket_promedio,
       MIN(fecha_hora) AS primera_venta,
       MAX(fecha_hora) AS ultima_venta
FROM ventas.venta;

-- 2. Ventas e ingresos por canal
SELECT tipo_venta,
       COUNT(*) AS cantidad_ventas,
       SUM(total_venta) AS ingresos,
       AVG(total_venta) AS ticket_promedio
FROM ventas.venta
GROUP BY tipo_venta
ORDER BY ingresos DESC;

-- 3. Ventas e ingresos por día
SELECT fecha_hora::date AS fecha,
       COUNT(*) AS cantidad_ventas,
       SUM(total_venta) AS ingresos
FROM ventas.venta
GROUP BY fecha_hora::date
ORDER BY fecha;

-- 4. Ventas e ingresos por mes
SELECT DATE_TRUNC('month', fecha_hora)::date AS mes,
       COUNT(*) AS cantidad_ventas,
       SUM(total_venta) AS ingresos
FROM ventas.venta
GROUP BY DATE_TRUNC('month', fecha_hora)
ORDER BY mes;

-- 5. Ventas e ingresos por hora del día
SELECT EXTRACT(HOUR FROM fecha_hora)::integer AS hora,
       COUNT(*) AS cantidad_ventas,
       SUM(total_venta) AS ingresos
FROM ventas.venta
GROUP BY EXTRACT(HOUR FROM fecha_hora)::integer
ORDER BY hora;

-- 6. Top 10 clientes por ingresos
SELECT c.id_cliente,
       c.nombre,
       COUNT(v.id_venta) AS cantidad_ventas,
       SUM(v.total_venta) AS ingresos
FROM ventas.cliente c
JOIN ventas.venta v ON v.id_cliente = c.id_cliente
GROUP BY c.id_cliente, c.nombre
ORDER BY ingresos DESC
LIMIT 10;

-- 7. Clientes sin compras registradas
SELECT c.id_cliente, c.nombre, c.email
FROM ventas.cliente c
LEFT JOIN ventas.venta v ON v.id_cliente = c.id_cliente
WHERE v.id_venta IS NULL
ORDER BY c.id_cliente;

-- 8. Rendimiento de empleados por ventas registradas
SELECT e.id_empleado,
       e.nombre,
       e.cargo,
       COUNT(v.id_venta) AS ventas_registradas,
       SUM(v.total_venta) AS ingresos_gestionados,
       AVG(v.total_venta) AS ticket_promedio
FROM ventas.empleado e
LEFT JOIN ventas.venta v ON v.id_empleado = e.id_empleado
GROUP BY e.id_empleado, e.nombre, e.cargo
ORDER BY ingresos_gestionados DESC NULLS LAST;

-- 9. Productos más vendidos por unidades
SELECT p.id_producto,
       p.nombre,
       p.categoria,
       SUM(d.cantidad) AS unidades_vendidas,
       SUM(d.subtotal) AS ingresos
FROM ventas.producto p
JOIN ventas.detalle_venta d ON d.id_producto = p.id_producto
GROUP BY p.id_producto, p.nombre, p.categoria
ORDER BY unidades_vendidas DESC, ingresos DESC;

-- 10. Producto líder por ingresos
SELECT p.id_producto,
       p.nombre,
       SUM(d.subtotal) AS ingresos
FROM ventas.producto p
JOIN ventas.detalle_venta d ON d.id_producto = p.id_producto
GROUP BY p.id_producto, p.nombre
ORDER BY ingresos DESC
LIMIT 1;

-- 11. Participación de cada producto en los ingresos
WITH ingresos AS (
    SELECT SUM(subtotal) AS total FROM ventas.detalle_venta
)
SELECT p.nombre,
       SUM(d.subtotal) AS ingresos_producto,
       ROUND(100.0 * SUM(d.subtotal) / NULLIF(i.total, 0), 2) AS participacion_pct
FROM ventas.producto p
JOIN ventas.detalle_venta d ON d.id_producto = p.id_producto
CROSS JOIN ingresos i
GROUP BY p.nombre, i.total
ORDER BY participacion_pct DESC;

-- 12. Rendimiento por categoría de producto
SELECT p.categoria,
       SUM(d.cantidad) AS unidades_vendidas,
       COUNT(DISTINCT d.id_venta) AS ventas_con_categoria,
       SUM(d.subtotal) AS ingresos
FROM ventas.producto p
JOIN ventas.detalle_venta d ON d.id_producto = p.id_producto
GROUP BY p.categoria
ORDER BY ingresos DESC;

-- 13. Ticket promedio por cliente frecuente/no frecuente
WITH compras_cliente AS (
    SELECT id_cliente, COUNT(*) AS compras
    FROM ventas.venta
    GROUP BY id_cliente
), clasificacion AS (
    -- El modelo relacional no almacena el atributo cliente_frecuente:
    -- se deriva como cliente con 100 o más ventas registradas.
    SELECT c.id_cliente,
           (COALESCE(k.compras, 0) >= 100) AS cliente_frecuente
    FROM ventas.cliente c
    LEFT JOIN compras_cliente k ON k.id_cliente = c.id_cliente
)
SELECT cl.cliente_frecuente,
       COUNT(v.id_venta) AS cantidad_ventas,
       AVG(v.total_venta) AS ticket_promedio,
       SUM(v.total_venta) AS ingresos
FROM clasificacion cl
JOIN ventas.venta v ON v.id_cliente = cl.id_cliente
GROUP BY cl.cliente_frecuente
ORDER BY cl.cliente_frecuente DESC;

-- 14. Distribución de ventas por cantidad de líneas de detalle
SELECT cantidad_lineas,
       COUNT(*) AS cantidad_ventas,
       AVG(total_venta) AS ticket_promedio
FROM (
    SELECT v.id_venta,
           v.total_venta,
           COUNT(d.id_detalle) AS cantidad_lineas
    FROM ventas.venta v
    JOIN ventas.detalle_venta d ON d.id_venta = v.id_venta
    GROUP BY v.id_venta, v.total_venta
) x
GROUP BY cantidad_lineas
ORDER BY cantidad_lineas;

-- 15. Ventas a domicilio por cliente y dirección
SELECT c.nombre,
       d.direccion_entrega,
       COUNT(v.id_venta) AS domicilios,
       SUM(v.total_venta) AS ingresos
FROM ventas.venta v
JOIN ventas.domicilio d ON d.id_domicilio = v.id_domicilio
JOIN ventas.cliente c ON c.id_cliente = v.id_cliente
WHERE v.tipo_venta = 'Domicilio'
GROUP BY c.nombre, d.direccion_entrega
ORDER BY domicilios DESC, ingresos DESC;

-- 16. Comparación de ingresos entre clientes frecuentes y no frecuentes por canal
WITH compras_cliente AS (
    SELECT id_cliente, COUNT(*) AS compras
    FROM ventas.venta
    GROUP BY id_cliente
), clasificacion AS (
    -- El modelo relacional no almacena el atributo cliente_frecuente:
    -- se deriva como cliente con 100 o más ventas registradas.
    SELECT c.id_cliente,
           (COALESCE(k.compras, 0) >= 100) AS cliente_frecuente
    FROM ventas.cliente c
    LEFT JOIN compras_cliente k ON k.id_cliente = c.id_cliente
)
SELECT cl.cliente_frecuente,
       v.tipo_venta,
       COUNT(*) AS cantidad_ventas,
       SUM(v.total_venta) AS ingresos
FROM ventas.venta v
JOIN clasificacion cl ON cl.id_cliente = v.id_cliente
GROUP BY cl.cliente_frecuente, v.tipo_venta
ORDER BY cl.cliente_frecuente DESC, ingresos DESC;

-- 17. Productos nunca vendidos
SELECT p.id_producto, p.nombre, p.categoria, p.precio_venta
FROM ventas.producto p
LEFT JOIN ventas.detalle_venta d ON d.id_producto = p.id_producto
WHERE d.id_detalle IS NULL
ORDER BY p.id_producto;

-- 18. Control de consistencia de totales por venta
SELECT v.id_venta,
       v.total_venta,
       SUM(d.subtotal) AS total_detalle,
       v.total_venta - SUM(d.subtotal) AS diferencia
FROM ventas.venta v
JOIN ventas.detalle_venta d ON d.id_venta = v.id_venta
GROUP BY v.id_venta, v.total_venta
HAVING v.total_venta <> SUM(d.subtotal)
ORDER BY ABS(v.total_venta - SUM(d.subtotal)) DESC;

-- 19. Clientes con eventos reservados y sus compras
WITH eventos_cliente AS (
    SELECT id_cliente, COUNT(*) AS eventos_reservados
    FROM ventas.evento
    GROUP BY id_cliente
), ventas_cliente AS (
    SELECT id_cliente,
           COUNT(*) AS cantidad_ventas,
           COALESCE(SUM(total_venta), 0) AS ingresos
    FROM ventas.venta
    GROUP BY id_cliente
)
SELECT c.id_cliente,
       c.nombre,
       e.eventos_reservados,
       COALESCE(v.cantidad_ventas, 0) AS cantidad_ventas,
       COALESCE(v.ingresos, 0) AS ingresos
FROM ventas.cliente c
JOIN eventos_cliente e ON e.id_cliente = c.id_cliente
LEFT JOIN ventas_cliente v ON v.id_cliente = c.id_cliente
ORDER BY eventos_reservados DESC, ingresos DESC;

-- 20. Agenda de eventos y clientes asociados
SELECT e.id_evento,
       t.nombre AS tipo_evento,
       e.fecha,
       e.hora_inicio,
       e.hora_final,
       e.ubicacion,
       c.id_cliente,
       c.nombre AS cliente,
       c.telefono
FROM ventas.evento e
JOIN ventas.tipo_evento t ON t.id_tipo_evento = e.id_tipo_evento
JOIN ventas.cliente c ON c.id_cliente = e.id_cliente
ORDER BY e.fecha, e.hora_inicio;

-- 21. Eventos ejecutados e ingresos por tipo de evento
SELECT t.id_tipo_evento,
       t.nombre AS tipo_evento,
       COUNT(e.id_evento) AS eventos_ejecutados,
       COALESCE(SUM(e.valor_contratado), 0) AS ingresos_eventos
FROM ventas.tipo_evento t
LEFT JOIN ventas.evento e ON e.id_tipo_evento = t.id_tipo_evento
GROUP BY t.id_tipo_evento, t.nombre
ORDER BY eventos_ejecutados DESC, ingresos_eventos DESC, t.nombre;

-- 22. Costos por mes y tipo de costo
SELECT DATE_TRUNC('month', fecha)::date AS mes,
       tipo_costo,
       SUM(monto) AS costo_total
FROM ventas.costo
GROUP BY DATE_TRUNC('month', fecha), tipo_costo
ORDER BY mes, tipo_costo;

-- 23. Rentabilidad por producto (ingresos vs. costo de producción)
WITH ing AS (
    SELECT id_producto, SUM(cantidad) AS unidades, SUM(subtotal) AS ingresos
    FROM ventas.detalle_venta
    GROUP BY id_producto
), cst AS (
    SELECT id_producto, SUM(monto) AS costo_produccion
    FROM ventas.costo
    WHERE tipo_costo = 'Producción'
    GROUP BY id_producto
)
SELECT p.id_producto,
       p.nombre,
       p.categoria,
       i.unidades,
       i.ingresos,
       COALESCE(c.costo_produccion, 0) AS costo_produccion,
       i.ingresos - COALESCE(c.costo_produccion, 0) AS margen_bruto,
       ROUND(100.0 * (i.ingresos - COALESCE(c.costo_produccion, 0)) / NULLIF(i.ingresos, 0), 2) AS margen_pct
FROM ventas.producto p
JOIN ing i ON i.id_producto = p.id_producto
LEFT JOIN cst c ON c.id_producto = p.id_producto
ORDER BY margen_bruto DESC;

-- 24. Estado de resultados mensual (ingresos - producción - gastos operativos)
WITH ing AS (
    SELECT DATE_TRUNC('month', fecha_hora)::date AS mes, SUM(total_venta) AS ingresos
    FROM ventas.venta
    GROUP BY DATE_TRUNC('month', fecha_hora)
), cst AS (
    SELECT DATE_TRUNC('month', fecha)::date AS mes,
           SUM(monto) FILTER (WHERE tipo_costo = 'Producción') AS costo_produccion,
           SUM(monto) FILTER (WHERE tipo_costo = 'Operativo')  AS gastos_operativos
    FROM ventas.costo
    GROUP BY DATE_TRUNC('month', fecha)
)
SELECT i.mes,
       i.ingresos,
       COALESCE(c.costo_produccion, 0) AS costo_produccion,
       COALESCE(c.gastos_operativos, 0) AS gastos_operativos,
       i.ingresos - COALESCE(c.costo_produccion, 0) - COALESCE(c.gastos_operativos, 0) AS utilidad,
       ROUND(100.0 * (i.ingresos - COALESCE(c.costo_produccion, 0) - COALESCE(c.gastos_operativos, 0))
             / NULLIF(i.ingresos, 0), 2) AS margen_pct
FROM ing i
LEFT JOIN cst c ON c.mes = i.mes
ORDER BY i.mes;

-- 25. Rentabilidad por evento
SELECT e.id_evento,
       t.nombre AS tipo_evento,
       e.fecha,
       c.nombre AS cliente,
       e.valor_contratado,
       COALESCE(SUM(k.monto), 0) AS costo_evento,
       e.valor_contratado - COALESCE(SUM(k.monto), 0) AS utilidad,
       ROUND(100.0 * (e.valor_contratado - COALESCE(SUM(k.monto), 0)) / NULLIF(e.valor_contratado, 0), 2) AS margen_pct
FROM ventas.evento e
JOIN ventas.tipo_evento t ON t.id_tipo_evento = e.id_tipo_evento
JOIN ventas.cliente c ON c.id_cliente = e.id_cliente
LEFT JOIN ventas.costo k ON k.id_evento = e.id_evento AND k.tipo_costo = 'Evento'
GROUP BY e.id_evento, t.nombre, e.fecha, c.nombre, e.valor_contratado
ORDER BY e.fecha;

-- 26. Rentabilidad por categoría de producto
WITH ing AS (
    SELECT p.categoria, SUM(d.cantidad) AS unidades, SUM(d.subtotal) AS ingresos
    FROM ventas.detalle_venta d
    JOIN ventas.producto p ON p.id_producto = d.id_producto
    GROUP BY p.categoria
), cst AS (
    SELECT p.categoria, SUM(k.monto) AS costo_produccion
    FROM ventas.costo k
    JOIN ventas.producto p ON p.id_producto = k.id_producto
    WHERE k.tipo_costo = 'Producción'
    GROUP BY p.categoria
)
SELECT i.categoria,
       i.unidades,
       i.ingresos,
       COALESCE(c.costo_produccion, 0) AS costo_produccion,
       ROUND(100.0 * (i.ingresos - COALESCE(c.costo_produccion, 0)) / NULLIF(i.ingresos, 0), 2) AS margen_pct
FROM ing i
LEFT JOIN cst c ON c.categoria = i.categoria
ORDER BY margen_pct DESC;
