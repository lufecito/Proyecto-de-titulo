Autoría de Luis Fontecilla

# Modelo de datos conceptual

## 1. Propósito

Definir las entidades y relaciones mínimas necesarias para mantener trazabilidad desde una solicitud externa hasta la ejecución y evaluación de una ruta. No corresponde todavía a un esquema físico ni fija nombres de tablas definitivos.

## 2. Entidades principales

### Usuario

Representa a una persona con acceso al sistema. Incluye identidad, credenciales o referencia al proveedor de identidad, rol, estado y fechas de actividad.

### Rol

Agrupa permisos para administrador, despachador y conductor. La autorización se aplica en el servidor.

### Ticket externo

Copia normalizada o referencia de una solicitud originada en el sistema existente. Conserva identificador externo, estado de sincronización, datos originales relevantes, fecha de actualización y errores de integración.

### Punto de recolección

Representa el lugar operativo asociado a una solicitud. Conserva dirección original, dirección normalizada, coordenadas, calidad de geocodificación, instrucciones y ventana horaria.

### Servicio de recolección

Unidad de trabajo que debe ser planificada. Relaciona el ticket, el punto, tipo y cantidad estimada de residuo, prioridad, tiempo de servicio, estado y restricciones.

### Vehículo

Representa un camión con identificación, capacidad, disponibilidad, tipo de carga admitida y punto de inicio o término cuando corresponda.

### Jornada

Agrupa la operación de un periodo determinado. Incluye fecha, zona, depósito, estado y responsables.

### Ruta

Asignación de un vehículo y conductor dentro de una jornada. Mantiene estado, versión publicada, estimaciones y resultados consolidados.

### Versión de ruta

Instantánea inmutable de una propuesta o publicación. Conserva el origen del cálculo, parámetros, secuencia, distancia, duración y usuario que la aceptó.

### Parada de ruta

Relaciona un servicio de recolección con una versión de ruta. Incluye posición planificada, tiempos estimados, estado operativo y resultado.

### Evento operacional

Registro cronológico de creación, publicación, llegada, recolección, incidencia, omisión, recalculo y cierre. Incluye fecha, actor, ubicación disponible, versión y datos mínimos del evento.

### Incidencia

Describe una condición que impide o modifica la recolección, por ejemplo punto no disponible, acceso bloqueado, exceso de capacidad o dirección incorrecta.

### Ejecución de optimización

Registra entrada identificable, configuración, versión del algoritmo, duración, resultado, advertencias y motivo de solicitudes no asignadas.

### Métrica de jornada

Almacena valores calculados para distancia, duración, cumplimiento, esperas, incidencias y comparación con la línea base.

## 3. Relaciones relevantes

- Un ticket externo puede originar uno o más servicios si el modelo del sistema existente lo permite; para el MVP se recomienda uno por solicitud salvo evidencia contraria.
- Un punto de recolección puede asociarse a varios servicios a lo largo del tiempo.
- Una jornada contiene varias rutas.
- Una ruta corresponde a un vehículo y puede tener un conductor asignado.
- Una ruta posee varias versiones y solo una versión publicada vigente.
- Una versión contiene varias paradas ordenadas.
- Un servicio puede aparecer en distintas propuestas, pero solo debe ejecutarse una vez en la jornada correspondiente.
- Una parada genera varios eventos operacionales y puede relacionarse con una incidencia.
- Una ejecución de optimización produce una propuesta identificable y reproducible.

## 4. Estados preliminares

### Servicio

Pendiente, validación requerida, disponible, asignado, en ejecución, completado, no realizado y cancelado.

### Ruta

Borrador, propuesta, publicada, en ejecución, pausada, completada y cancelada.

### Parada

Pendiente, próxima, en atención, completada, no disponible, omitida e incidencia.

Los cambios permitidos deben implementarse como una máquina de estados validada en el servidor. Las correcciones administrativas deben mantener auditoría.

## 5. Integridad y trazabilidad

- Identificador externo único por sistema de origen.
- Coordenadas con sistema de referencia explícito.
- Fechas y horas con zona horaria.
- Versiones de ruta inmutables después de su publicación.
- Eventos idempotentes para sincronización móvil.
- Borrado lógico o política de retención para registros operacionales.
- Restricciones de unicidad que impidan completar dos veces el mismo servicio.
- Registro de usuario y causa para ajustes manuales.

## 6. Datos mínimos para optimizar

- Identificador de servicio.
- Coordenadas validadas.
- Estado de disponibilidad.
- Prioridad.
- Tiempo estimado de atención.
- Ventana horaria, si existe.
- Demanda o volumen estimado, si la capacidad forma parte del escenario.
- Vehículos disponibles, capacidad y ubicación inicial.
- Matriz de distancia o tiempo entre puntos.

## 7. Datos que no deben asumirse

Antes del diseño físico se debe confirmar la unidad de capacidad, tipos de residuos incompatibles, depósitos, turnos, ventanas horarias, precisión de ubicación, datos personales necesarios y política de conservación.
