Autoría de Luis Fontecilla

# Decisiones pendientes

## 1. Propósito

Registrar decisiones que afectan el alcance, la arquitectura o la evaluación. Ninguna alternativa indicada en esta documentación se considera definitiva hasta que tenga responsable, evidencia y fecha de resolución.

## 2. Decisiones prioritarias

### DP-01. Contrato con el sistema de tickets

Definir si la integración será por API, webhooks, lectura autorizada de base de datos o exportación programada. Confirmar campos, autenticación, frecuencia, estados y propiedad de la información.

### DP-02. Usuario objetivo del MVP

Confirmar si la demostración priorizará al despachador, al conductor o ambos. Esta decisión modifica el esfuerzo de interfaz y las pruebas de conectividad móvil.

### DP-03. Proveedor cartográfico

Comparar cobertura, geocodificación, matrices, tráfico, costo, cuotas, licencia y condiciones de almacenamiento. Preparar una prueba con direcciones reales de la zona objetivo.

### DP-04. Definición del costo a optimizar

Acordar si la función objetivo utiliza distancia, tiempo, combustible, prioridad, incumplimiento de ventana o una combinación ponderada. Cada peso debe justificarse.

### DP-05. Restricciones operacionales

Confirmar capacidad, turnos, depósitos, tipos de residuo, tiempos de servicio, ventanas horarias, descansos y restricciones de circulación.

### DP-06. Volumen esperado

Determinar cantidad de tickets diarios, vehículos simultáneos, usuarios concurrentes y frecuencia de recalculo. Estos datos orientan la arquitectura y las pruebas.

### DP-07. Datos para la línea base

Confirmar disponibilidad de rutas históricas o acceso a un operador que construya rutas manuales comparables.

### DP-08. Operación con conectividad limitada

Definir si el conductor requiere consulta y registro temporal sin conexión. Si es obligatorio, debe entrar tempranamente al diseño.

### DP-09. Tecnología de implementación

Seleccionar frontend, backend, motor de optimización y estrategia de despliegue mediante criterios explícitos, una vez confirmado el alcance.

### DP-10. Protección y retención de datos

Identificar datos personales, periodo de conservación, responsables, usuarios autorizados y procedimiento de eliminación o anonimización.

## 3. Formato para registrar una decisión

- Identificador y título.
- Estado: propuesta, aceptada, rechazada o reemplazada.
- Fecha y responsables.
- Contexto y restricciones.
- Alternativas consideradas.
- Decisión y justificación.
- Consecuencias positivas y negativas.
- Evidencia o prueba técnica asociada.

## 4. Orden recomendado de resolución

Primero deben resolverse DP-01, DP-02, DP-04, DP-05 y DP-07. Con esa información se puede cerrar el alcance medible. Luego se resuelven DP-03, DP-06, DP-08 y DP-09. La protección de datos debe revisarse durante todo el proceso y formalizarse antes de utilizar información real.
