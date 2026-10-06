-- ============================================================================
-- Restaurante El Buen Sazón - Script de creación e inserción de datos (v2)
-- Motor: PostgreSQL | Esquema: ventas
-- Cambios v2: tabla tipo_evento (entidad extraída de evento), tabla costo
-- (producción, operativos y eventos), nuevos productos (gaseosas, cervezas,
-- acompañantes) y datos de apoyo inventados para tipo_evento, evento y costo.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS ventas;

CREATE TABLE ventas.cliente (
    id_cliente   integer PRIMARY KEY,
    nombre       varchar(150) NOT NULL,
    direccion    varchar(300),
    telefono     varchar(30),
    email        varchar(255) UNIQUE
);

CREATE TABLE ventas.empleado (
    id_empleado  integer PRIMARY KEY,
    nombre       varchar(150) NOT NULL,
    cargo        varchar(100) NOT NULL,
    telefono     varchar(30)
);

CREATE TABLE ventas.producto (
    id_producto  integer PRIMARY KEY,
    nombre       varchar(150) NOT NULL,
    descripcion  text,
    categoria    varchar(80) NOT NULL,   -- Desayuno, Almuerzo, Gaseosa, Cerveza, Acompañante
    precio_venta numeric(12,2) NOT NULL CHECK (precio_venta >= 0)
);

CREATE TABLE ventas.domicilio (
    id_domicilio      integer PRIMARY KEY,
    fecha_hora        timestamp NOT NULL,
    direccion_entrega varchar(300) NOT NULL,
    telefono_contacto varchar(30)
);

CREATE TABLE ventas.tipo_evento (
    id_tipo_evento integer PRIMARY KEY,
    nombre         varchar(100) NOT NULL UNIQUE,
    descripcion    text
);

CREATE TABLE ventas.evento (
    id_evento        integer PRIMARY KEY,
    id_tipo_evento   integer NOT NULL REFERENCES ventas.tipo_evento (id_tipo_evento),
    fecha            date NOT NULL,
    hora_inicio      time NOT NULL,
    hora_final       time NOT NULL,
    ubicacion        varchar(300) NOT NULL,
    id_cliente       integer NOT NULL REFERENCES ventas.cliente (id_cliente),
    valor_contratado numeric(12,2) NOT NULL CHECK (valor_contratado >= 0),
    CONSTRAINT ck_evento_horario CHECK (hora_final > hora_inicio)
);

CREATE TABLE ventas.venta (
    id_venta     integer PRIMARY KEY,
    fecha_hora   timestamp NOT NULL,
    id_cliente   integer NOT NULL REFERENCES ventas.cliente (id_cliente),
    id_empleado  integer NOT NULL REFERENCES ventas.empleado (id_empleado),
    tipo_venta   varchar(20) NOT NULL CHECK (tipo_venta IN ('Local', 'Domicilio')),
    id_domicilio integer REFERENCES ventas.domicilio (id_domicilio),
    total_venta  numeric(12,2) NOT NULL CHECK (total_venta >= 0),
    CONSTRAINT ck_venta_domicilio CHECK (
        (tipo_venta = 'Local' AND id_domicilio IS NULL) OR
        (tipo_venta = 'Domicilio' AND id_domicilio IS NOT NULL))
);

CREATE TABLE ventas.detalle_venta (
    id_detalle   integer PRIMARY KEY,
    id_venta     integer NOT NULL REFERENCES ventas.venta (id_venta) ON DELETE CASCADE,
    id_producto  integer NOT NULL REFERENCES ventas.producto (id_producto),
    cantidad     integer NOT NULL CHECK (cantidad > 0),
    subtotal     numeric(12,2) NOT NULL CHECK (subtotal >= 0)
);

-- Costos: 'Producción' (por producto y mes), 'Operativo' (fijos/mensuales) y 'Evento'
CREATE TABLE ventas.costo (
    id_costo    integer PRIMARY KEY,
    fecha       date NOT NULL,
    tipo_costo  varchar(20) NOT NULL CHECK (tipo_costo IN ('Producción', 'Operativo', 'Evento')),
    concepto    varchar(200) NOT NULL,
    id_producto integer REFERENCES ventas.producto (id_producto),
    id_evento   integer REFERENCES ventas.evento (id_evento),
    monto       numeric(12,2) NOT NULL CHECK (monto >= 0),
    CONSTRAINT ck_costo_referencia CHECK (
        (tipo_costo = 'Producción' AND id_producto IS NOT NULL AND id_evento IS NULL) OR
        (tipo_costo = 'Evento'     AND id_evento  IS NOT NULL AND id_producto IS NULL) OR
        (tipo_costo = 'Operativo'  AND id_producto IS NULL AND id_evento IS NULL))
);

CREATE INDEX ix_venta_cliente    ON ventas.venta (id_cliente);
CREATE INDEX ix_venta_empleado   ON ventas.venta (id_empleado);
CREATE INDEX ix_venta_fecha      ON ventas.venta (fecha_hora);
CREATE INDEX ix_venta_tipo       ON ventas.venta (tipo_venta);
CREATE INDEX ix_evento_cliente   ON ventas.evento (id_cliente);
CREATE INDEX ix_evento_tipo      ON ventas.evento (id_tipo_evento);
CREATE INDEX ix_evento_fecha     ON ventas.evento (fecha);
CREATE INDEX ix_detalle_venta    ON ventas.detalle_venta (id_venta);
CREATE INDEX ix_detalle_producto ON ventas.detalle_venta (id_producto);
CREATE INDEX ix_costo_fecha      ON ventas.costo (fecha);
CREATE INDEX ix_costo_tipo       ON ventas.costo (tipo_costo);

-- Seguridad: RLS activo y sin políticas (la app accede por conexión directa a Postgres,
-- así nada queda expuesto por la API REST de Supabase).
ALTER TABLE ventas.cliente ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas.empleado ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas.producto ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas.domicilio ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas.tipo_evento ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas.evento ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas.venta ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas.detalle_venta ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas.costo ENABLE ROW LEVEL SECURITY;
