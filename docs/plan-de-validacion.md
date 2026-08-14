Autoría de Luis Fontecilla

# Plan de validación

## 1. Objetivo

Demostrar que el sistema funciona de extremo a extremo y que la propuesta de rutas aporta una mejora medible frente a una planificación de referencia, sin atribuir al algoritmo beneficios que no estén respaldados por datos.

## 2. Pregunta de evaluación

En un conjunto representativo de solicitudes de recolección, bajo las mismas restricciones y vehículos, ¿la ruta propuesta por el sistema reduce el costo operacional definido sin disminuir el cumplimiento de los servicios?

## 3. Línea base

La línea base debe definirse antes de evaluar resultados. Las opciones preferentes son una ruta histórica ejecutada, una ruta planificada manualmente por un operador o una regla simple reproducible. No se deben comparar escenarios con entradas o restricciones distintas.

## 4. Métricas

- Distancia total planificada y ejecutada.
- Duración total planificada y ejecutada.
- Tiempo de espera o improductivo.
- Cantidad y porcentaje de servicios completados.
- Servicios fuera de ventana horaria.
- Servicios no asignados y motivo.
- Recalculos realizados durante la jornada.
- Diferencia entre estimación y ejecución.
- Tiempo de cálculo del algoritmo.
- Costo monetario estimado, solo si los supuestos de cálculo están documentados.

## 5. Escenarios de prueba

### Escenario A. Flujo nominal

Tickets válidos, ubicaciones correctas, un vehículo y todos los puntos disponibles.

### Escenario B. Punto no disponible

Una parada cambia de estado durante la ejecución. Se verifica que solo se reordenen las pendientes y que la ruta publicada anterior quede en el historial.

### Escenario C. Dirección inválida

Una solicitud no puede geocodificarse. Debe quedar en revisión y no provocar un cálculo incorrecto.

### Escenario D. Capacidad insuficiente

La demanda supera la capacidad disponible. El sistema debe informar servicios no asignados y su causa.

### Escenario E. Ventanas horarias

Existen puntos que solo pueden atenderse en intervalos específicos. La solución debe detectar incumplimientos o inviabilidad.

### Escenario F. Proveedor cartográfico no disponible

Se comprueba la respuesta controlada, el uso permitido de datos previamente obtenidos y la conservación de la última ruta publicada.

### Escenario G. Conectividad intermitente

El conductor registra eventos repetidos o retrasados. El sistema debe evitar duplicación y conservar el orden temporal.

## 6. Pruebas requeridas

- Pruebas unitarias de reglas y cálculo de costos.
- Pruebas de integración con tickets, mapas y base de datos.
- Pruebas de contrato para campos y errores de servicios externos.
- Pruebas de extremo a extremo para los flujos principales.
- Pruebas de seguridad para permisos, sesiones, entradas y secretos.
- Pruebas de respaldo y restauración.
- Pruebas de rendimiento con el volumen esperado del proyecto.
- Pruebas de usabilidad con al menos un perfil de despachador y uno de conductor cuando sea posible.

## 7. Conjunto de datos

Debe mantenerse un conjunto anonimizado y versionado con ubicaciones, vehículos, restricciones y resultados esperados. Si se utilizan datos reales, se deben retirar identificadores personales y documentar su autorización. También se requieren escenarios sintéticos para casos límite.

## 8. Reproducibilidad

Cada ejecución evaluada debe registrar versión del algoritmo, parámetros, conjunto de entrada, proveedor o matriz utilizada, fecha, duración y resultado. La ruta manual utilizada como referencia también debe quedar almacenada.

## 9. Criterio de aprobación

El MVP se considera validado cuando completa los escenarios obligatorios sin pérdida de trazabilidad, respeta las restricciones definidas y muestra una mejora o, como mínimo, evidencia cuantitativa clara sobre cuándo el optimizador aporta valor y cuándo no.

La meta porcentual de mejora no se fija en esta etapa porque depende de la calidad de los datos, la operación real y la línea base. Debe acordarse después de una medición exploratoria.

## 10. Evidencias a conservar

- Conjunto de datos de prueba y su versión.
- Configuración de cada ejecución.
- Resultado de la línea base.
- Resultado optimizado.
- Registros de errores e incidencias.
- Capturas o reportes de los flujos principales.
- Informe final con limitaciones y amenazas a la validez.
