# Módulo de recolección

Planificación de rutas de recolección, optimización local y seguimiento en
terreno, integrado en Ticket Kanban (Flask + CoreUI). El módulo vive en
`apps/recoleccion/` y se registra bajo las rutas `/recoleccion` y
`/api/v1/recoleccion`.

## Roles

- **Administrador**: acceso total (planificación, vehículos, históricos).
- **Despachador**: gestiona solicitudes, vehículos, jornadas y publica rutas.
- **Conductor**: ve su "Mi ruta" y reporta eventos en las paradas asignadas.

Los decoradores `despachador_required` y `conductor_o_despachador` controlan
el acceso (403 si no corresponde). En las vistas, la navegación se agrega
según el rol en `apps/templates/includes/{sidebar,navigation}.html`.

## Puesta en marcha

```bash
pip install -r requirements.txt
cp .env.example .env
flask --app run.py create-admin
flask --app run.py seed-routing-demo   # datos de demostración idempotentes
flask --app run.py run
```

La semilla crea: 3 usuarios demo (`demo-admin`, `demo-despachador`,
`demo-conductor`, contraseña `Demo1234!` por defecto), un cliente, 8
solicitudes, el vehículo `CAM-01` (capacidad 1000 kg) y una jornada para hoy.

## Cartografía

La clave de openrouteservice **nunca sale del servidor**. La selección del
proveedor se hace por entorno:

| MAP_PROVIDER | Comportamiento |
|---|---|
| `auto` | ORS si existe `ORS_API_KEY`, si no modo demostración sin red |
| `ors` | Exige `ORS_API_KEY` (falla si no está) |
| `fake` | Modo demostración sin red (estimaciones no viales) |

Ver `.env.example` para las variables disponibles (perfiles, país de
geocodificación, teselas Leaflet, límites de Chile, timeouts, caché persistente
en `MAP_CACHE_DIR`). El mapa web usa Leaflet con teselas configurables y una
capa opcional de límites de Chile.

## Optimización

`apps/recoleccion/services/optimizer.py`:

1. **Línea base** `NearestNeighborBaseline` (heurística simple, siempre se
   ejecuta).
2. **Propuesta** `ORToolsVRPOptimizer` (OR-Tools 9.x, matriz de viaje del
   proveedor, demanda por solicitud ≤ capacidad del vehículo, con
   `SetGlobalSpanCostCoefficient` para compactar rutas).

Cada ejecución registra `EjecucionOptimizacion` y versiones inmutables
(`RutaVersion`): `linea_base`, `propuesta`, `publicada`. Las solicitudes que
no caben se listan como `no_asignadas` con su motivo (`capacidad`,
`sin_vehiculos`, `sin_coordenadas`, ...).

`apps/recoleccion/services/planning.py`:

- `optimizar_jornada(jornada_id)` — recalcula línea base + propuesta por
  vehículo y crea/actualiza las rutas en estado `propuesta`.
- `publicar_version(ruta_id, version_id)` — copia inmutable tipo `publicada`,
  queda vigente y marca la jornada como `publicada`. Es idempotente.
- `recalcular_ruta(ruta_id)` — re-optimiza conservando las paradas
  completadas en su posición; descarta las ya atendidas de los pendientes.

## API (JSON + CSRF)

Los métodos de escritura del blueprint exigen el encabezado `X-CSRFToken`
(los formularios FlaskForm validan su propio token oculto). El token se
expone en el meta `name="csrf-token"`.

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/v1/recoleccion/geocodificar` | POST | `{direccion}` → lat/lon |
| `/api/v1/recoleccion/reversa` | POST | `{lat, lon}` → dirección |
| `/api/v1/recoleccion/paradas/<id>/evento` | POST | Evento de parada |
| `/api/v1/recoleccion/rutas/<id>/publicar` | POST | Publica `{version_id}` |
| `/api/v1/recoleccion/rutas/<id>/recalcular` | POST | Re-optimiza pendientes |
| `/api/v1/recoleccion/rutas/<id>/version/<vid>` | GET | Detalle de versión |
| `/api/v1/recoleccion/estado-proveedor` | GET | Estado del proveedor |

Eventos de parada (`llegada`, `recoleccion_completada`,
`punto_no_disponible`, `incidencia`) con `idempotencia_key`: un evento duplicado
devuelve `duplicado: true` sin crear un registro nuevo. Un conductor solo puede
reportar en sus propias rutas y en la versión vigente (403/409 en otro caso).

## Ejecución en terreno

`/recoleccion/mi-ruta` muestra el mapa con la ruta vigente, la tabla de paradas
y los botones de evento para el conductor. `/recoleccion/mapa-ruta/<id>`
muestra la ruta a despachadores/administradores. Los eventos quedan auditados
en `EventoRuta` y se listan en `/recoleccion/historial`.

## Migraciones y PostgreSQL

La versión inicial `migrations/versions/9f4c2a7b1e00_recoleccion.py` crea las
11 tablas del módulo y es **idempotente** (revisa el esquema existente con
`inspector`), por lo que también puede aplicarse sobre una base ya creada con
`db.create_all()`. En SQLite no soporta `ALTER TABLE ... ADD CONSTRAINT`, así
que la FK circular de `rutas.version_vigente_id` se omite en ese dialecto.

Con Docker Compose (perfil postgres):

```bash
docker compose --profile postgres up --build
```

Levanta `db` (PostgreSQL 16) con healthcheck y `ticketflow-postgres`; el
entrypoint ejecuta `flask db upgrade` antes de iniciar gunicorn. Sin
`--profile` se mantiene el comportamiento por defecto con SQLite en un
volumen. Variables relevantes: `DB_ENGINE`, `DB_NAME`, `DB_HOST`, `DB_PORT`,
`DB_USERNAME`, `DB_PASS` (ver `.env.example`).

## Pruebas

Sin internet (proveedor `fake`) y con base SQLite temporal:

```bash
# suite unitaria / de integración (49 tests)
python -m unittest discover -s tests -p "test_*.py"

# flujo completo de demostración (optimizar → publicar → recalcular)
python tests/flow_test.py

# renderizado de todas las páginas + CSRF de la API
python tests/render_test.py

# smoke test global de la aplicación
python tests/smoke_test.py
```
