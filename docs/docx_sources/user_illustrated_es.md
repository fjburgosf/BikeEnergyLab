# Manual de usuario de BikeEnergyLab

## 1. Introducción

### 1.1 Propósito del software

BikeEnergyLab 1.0.0 permite configurar una bicicleta eléctrica, simular rutas y estudiar energía, autonomía, calibración e incertidumbre. Este manual explica su operación con capturas de la interfaz real y nueve ejercicios sintéticos. La metodología desarrolla las ecuaciones y el manual técnico explica la implementación.

### 1.2 Contexto general

El programa calcula la demanda necesaria para seguir una velocidad prescrita y comprueba potencia y batería. Wh es energía. Wh/km es consumo por distancia. SOC es una fracción entre 0 y 1. Los datos incluidos son sintéticos y no establecen precisión con una bicicleta real.

### 1.3 Alcance del documento

La revisión editorial del 7 de octubre de 2026 cubre los quince paneles, los botones, el tutorial y los ejemplos. El flujo utiliza **Cargar ejemplo** y después **Simular**. La selección del desplegable describe un caso. Cargarlo lo convierte en el ejemplo activo. Las capturas corresponden al mismo código de interfaz que el EXE.

## 2. Descripción general del sistema

### 2.1 Hardware y requisitos del sistema

El paquete comprobado es Windows x64. Conserve BikeEnergyLab.exe, _internal y toda la carpeta. No requiere Python instalado, conexión, bicicleta conectada ni GPU. Desde fuentes, necesita Python 3.11 o superior y las dependencias de pyproject.toml. El costo del cálculo depende de segmentos, rutas y muestras.

### 2.2 Qué hace el sistema

Combina física longitudinal, aporte humano, pérdidas y batería. Produce energía, consumo, SOC, potencias, balance y factibilidad. Importa CSV/GPX, convierte telemetría, calibra, entrena y adapta CGPRA, analiza incertidumbre y sensibilidad, y exporta datos y procedencia.

### 2.3 Principales capacidades

| Flujo | Resultado que debe revisar |
| --- | --- |
| Simulación | Energía, SOC, finalización y potencia suficiente |
| Calibración | Parámetros, residuos e identificabilidad |
| Modelo híbrido | M1 a M4, alpha, soporte OOD e intervalos |
| Monte Carlo | Dispersión, misión, reserva y autonomía censurada |
| Experimentos | Dominios, semillas, comparaciones y límites |
| Exportación | YAML, CSV, JSON, figuras y metadatos |

## 3. Acceso y requisitos

### 3.1 Ejecución del paquete portátil

En Entregables encontrará cinco documentos Word y dos ZIP. Extraiga BikeEnergyLab-1.0.0-windows-x64.zip fuera de Entregables y abra BikeEnergyLab.exe en la carpeta BikeEnergyLab extraída. Conserve la carpeta completa con _internal. Inicio presenta ejemplos y tutorial. El selector superior derecho permite elegir es o en.

### 3.2 Ejecución desde fuentes

Descomprima el ZIP de fuentes y abra una terminal en la raíz del proyecto. Los comandos siguientes se ejecutan en una terminal, no en campos de la aplicación.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m bikeenergylab gui
```

Versión: 1.0.0. Contacto: fjburgosf@gmail.com.

## 4. Uso del sistema

### 4.1 Inicio y controles generales

{{IMAGE:docs/images/gui-1.0.0/01-inicio.png|Pantalla inicial con barra superior, navegación y catálogo de ejemplos.}}

La navegación izquierda cambia de panel. La barra inferior informa Listo, Calculando o errores. Mientras calcula se bloquean los controles. Espere a Listo. Las barras de desplazamiento permiten revisar campos inferiores.

| Control | Acción y uso |
| --- | --- |
| Abrir YAML | Abre y valida una configuración. Descarta el contexto del ejemplo activo. |
| Guardar YAML | Guarda la configuración actual. Exporte los resultados por separado. |
| Simular | Lee parámetros y ejecuta el procedimiento del caso activo: física, calibración, incertidumbre o entrenamiento híbrido inicial. |
| Ejemplos | Regresa a Inicio y enfoca el selector. |
| Tutorial | Abre la guía de ocho pasos. |
| Selector es/en | Cambia el idioma conservando el paso de la guía. |
| Navegación izquierda | Abre un panel sin ejecutar un cálculo. |
| X de la ventana | Cierra la aplicación. Guarde y exporte antes de cerrar. |

### 4.2 Selección y carga de ejemplos

Seleccione el caso en el desplegable, lea la descripción, pulse **Cargar ejemplo**, revise **Ejemplo activo** y pulse **Simular**. Cargar sustituye configuración, resultado y modelo en memoria. Conserva los archivos guardados. Cambiar solo la selección no sustituye el caso activo. **Iniciar tutorial guiado** abre la misma guía que Tutorial. Un modelo híbrido ya entrenado se reutiliza al simular otra vez. Cargar otro ejemplo lo descarta.

### 4.3 Bicicleta y ciclista

{{IMAGE:docs/images/gui-1.0.0/panel-bike.png|Panel Bicicleta con masas, rodadura, aerodinámica y transmisión.}}

Configure masa, carga, CdA, Crr, radio y eficiencia de transmisión. La masa total incluye bicicleta, ciclista y carga. Los valores iniciales son supuestos editables. Las ayudas indican unidades y rangos orientativos. El programa valida restricciones al ejecutar.

{{IMAGE:docs/images/gui-1.0.0/panel-rider.png|Panel Ciclista con masa y potencia humana en pedales.}}

Configure masa y potencia humana. Se define en pedales y puede ser constante, temporal o dependiente de cadencia, pendiente y fatiga. Los coeficientes iniciales de este último modo no representan una validación fisiológica. El aporte sobrante no carga la batería.

### 4.4 Motor y batería

{{IMAGE:docs/images/gui-1.0.0/panel-motor.png|Panel Motor con asistencia, eficiencia y límites.}}

Configure asistencia demand o proportional, eficiencia, potencia mecánica, torque equivalente y velocidad de corte. El mapa CSV usa velocidad angular equivalente v/r y torque. Los puntos fuera del mapa se acotan a la frontera y se señalan.

{{IMAGE:docs/images/gui-1.0.0/panel-battery.png|Panel Batería con capacidad, SOC y parámetros del modelo.}}

Configure Wh nominales, fracción utilizable y SOC inicial/mínimo. Por ejemplo, 500 Wh, fracción 0.95 y SOC de 0.90 a 0.10 representan 380 Wh disponibles. Energy y soc comparten la contabilidad energética. ECM añade Ah, OCV, resistencias, rama RC y límites eléctricos. Cambiar Wh no cambia Ah automáticamente. Desplace el panel para ver los campos inferiores. Las casillas activan opciones booleanas. Revise su ayuda y límites. Las curvas térmicas necesitan datos de la batería concreta.

### 4.5 Ruta

{{IMAGE:docs/images/gui-1.0.0/panel-route.png|Panel Ruta con creación manual, importación y vista previa.}}

| Botón | Procedimiento |
| --- | --- |
| Crear ruta manual | Introduzca distancia en m, velocidad en m/s y pendiente elevación/horizontal. Pulse para construir. 0.03 significa 3%. |
| Abrir ruta CSV | Seleccione length_m, dt_s, speed_mps y grade coherentes. Se informan inconsistencias. |
| Abrir GPX | Seleccione la traza. Con tiempos se derivan velocidades y paradas. Sin tiempos hace falta velocidad supuesta. |
| Visualizar ruta | Muestra el perfil para revisar distancia, velocidad y elevación antes de simular. |

Los perfiles temporales tienen prioridad sobre escalares. Prepare las uniones de segmentos y revise el suavizado registrado. Después de crear/importar, pulse Simular.

### 4.6 Ambiente física y simulación

{{IMAGE:docs/images/gui-1.0.0/panel-environment.png|Panel Ambiente con viento y condiciones del aire.}}

Viento positivo es posterior y negativo es frontal. Configure temperatura y presión/densidad. Sin curva térmica de batería, el ejemplo frío no implica pérdida de capacidad por frío.

{{IMAGE:docs/images/gui-1.0.0/panel-physics.png|Panel Física con fuerzas, potencia y balance.}}

La regeneración está desactivada por defecto y exige hardware capaz, límites eléctricos y margen de SOC. Revise sus opciones en los campos o YAML antes de activarla. No reste dos veces la energía de descenso.

{{IMAGE:docs/images/gui-1.0.0/panel-simulation.png|Panel Simulación con paso temporal y opciones numéricas.}}

Configure timestep y auxiliares. Reducir el paso permite estudiar convergencia, pero aumenta el trabajo. Simular calcula. Una ruta limitada por potencia no significa que se haya realizado el perfil completo.

### 4.7 Calibración y telemetría

{{IMAGE:docs/images/gui-1.0.0/panel-calibration.png|Panel Calibración con ajuste y conversión de sensores.}}

**Calibrar desde CSV observado** carga observaciones de rutas completas, ajusta Crr/CdA y muestra residuos e identificabilidad. Use grupos route_id independientes, intervalos y observed_route_energy_wh. Conserve las condiciones de cada ruta. Un error pequeño no garantiza identificación física.

**Convertir CSV de sensores** deriva velocidad de distancia/tiempo e integra potencia terminal V por I entre muestras. Revise unidades y advertencias antes de ajustar un modelo. datasets/telemetry_example.csv es una práctica sintética.

### 4.8 Modelo híbrido

{{IMAGE:docs/images/gui-1.0.0/panel-hybrid.png|Panel Modelo híbrido con entrenamiento, archivos, adaptación e intervalos.}}

| Botón | Acción y condición |
| --- | --- |
| Entrenar CGPRA desde CSV | Aprende con rutas observadas independientes. Necesita al menos 40 rutas separadas entre entrenamiento e intervalos. |
| Entrenar demostración sintética | Genera datos de práctica y entrena. No usa mediciones reales. |
| Abrir modelo CGPRA guardado | Selecciona la carpeta completa y verifica reconstrucción y replay. |
| Guardar modelo CGPRA reutilizable | Crea una carpeta nueva con CSV, JSON y mapas. Conserve todo. |
| Adaptar modelo con rutas observadas nuevas | Actualiza con rutas nuevas e invalida intervalos previos. |
| Recalibrar intervalos con rutas nuevas | Usa rutas independientes frescas para recuperar intervalos después de adaptar. |

M1 es físico, M2 datos, M3 residual fijo y M4 CGPRA. Alpha es un peso, no probabilidad de acierto. OOD examina soporte sin garantizar exactitud. Tras adaptar, use predicciones puntuales hasta recalibrar con datos nuevos. No reutilice grupos retenidos como rutas nuevas.

### 4.9 Incertidumbre

{{IMAGE:docs/images/gui-1.0.0/panel-uncertainty.png|Panel Incertidumbre con editor YAML y misión/autonomía.}}

Edite distribuciones, muestras, semilla, reserva y horizonte. **Aplicar YAML** valida y activa ese texto. Escribir sin aplicar no cambia el caso. **Misión / autonomía** ejecuta Monte Carlo y calcula finalización con potencia y reserva, bandas físicas y autonomía. Revise cuántas muestras llegan a cada punto y la censura al superar el horizonte.

Con un CGPRA calibrado se añade demanda predictiva. energy_budget_probability evalúa presupuesto energético y no sustituye mission_probability ni corrige SOC, voltaje o corriente. No extrapole trayectorias después del agotamiento.

### 4.10 Experimentos y sensibilidad

{{IMAGE:docs/images/gui-1.0.0/panel-experiments.png|Panel Experimentos con benchmark, sensibilidad y suite.}}

**Ejecutar benchmark ID/OOD** compara modelos, compuertas y ablaciones con grupos independientes. **Analizar sensibilidad** ejecuta el método del selector: OAT, Spearman, Morris o Sobol. Revise dominios, muestras y semilla. Sobol ordinario requiere entradas independientes. **Ejecutar EXP-01–15** realiza los quince protocolos sintéticos. No compare métricas de protocolos distintos como si pertenecieran a la misma prueba.

### 4.11 Resultados y controles de gráficos

{{IMAGE:docs/images/gui-1.0.0/resultado-plano.png|Resultado ejecutado del ejemplo plano con resumen y gráficos.}}

Revise energy_wh, wh_per_km, final_soc, completed_route, feasible y demanda no satisfecha. Demanda de la ruta completa, consumo hasta agotamiento, autonomía estacionaria y misión tienen significados diferentes.

| Botón de Matplotlib | Función |
| --- | --- |
| Home | Restablece la vista original. |
| Back | Vuelve a la vista anterior. |
| Forward | Avanza en el historial de vistas. |
| Pan | Activa desplazamiento con ratón. Pulse otra vez para desactivar. |
| Zoom | Activa selección de una región para ampliar. |
| Subplots | Abre ajustes de márgenes y separación. |
| Save | Guarda esa figura. Seleccione PNG, SVG o PDF. |

Estos nombres pueden permanecer en inglés. Save conserva una figura. La exportación completa conserva además datos, configuración y procedencia.

### 4.12 Exportación y cierre

{{IMAGE:docs/images/gui-1.0.0/panel-export.png|Panel Exportar con el botón para conservar el último resultado.}}

Pulse **Exportar último resultado**, elija una carpeta y conserve el directorio EXP nuevo completo con YAML, CSV, JSON, figuras y recursos copiados. Abrir/Guardar confirma un diálogo. Cancelar abandona la selección sin ejecutar la operación. Antes de cerrar con X, guarde y exporte. No existe un botón específico de pausa/reanudación científica en esta versión.

### 4.13 Tutorial integrado

{{IMAGE:docs/images/gui-1.0.0/tutorial-inicio.png|Tutorial con acción contextual, Anterior, Siguiente y Cerrar tutorial.}}

**Anterior** retrocede, **Siguiente** avanza y **Cerrar tutorial** cierra la guía manteniendo el caso. El botón contextual cambia según el paso y ejecuta la acción descrita. Si necesita un resultado, simule primero y vuelva al paso.

{{TUTORIAL}}

### 4.14 Ejemplos de funcionamiento

En cada ejercicio: Ejemplos, selección, Cargar ejemplo, revisión de Ejemplo activo, Simular y Resultados. Las siguientes capturas se tomaron tras ejecutar cada caso. Sus valores corresponden a prácticas sintéticas, no a mediciones de campo.

{{EXAMPLES}}

## 5. Solución de problemas

### 5.1 La selección parece no ejecutarse

Revise Ejemplo activo. Seleccionar solo modifica la descripción. Pulse Cargar ejemplo y Simular. Para un caso propio, abra su YAML y cree/importe la ruta. Después de editar el YAML de Incertidumbre, pulse Aplicar YAML.

### 5.2 Entrada o archivo rechazado

Revise nombres, unidades, límites y length_m = speed_mps por dt_s. SOC 38% es 0.38, pendiente 3% es 0.03 y viento frontal es negativo. Ciertos perfiles temporales impiden distribuciones escalares incompatibles. Conserve el mensaje de error.

### 5.3 Modelo o intervalos inválidos

Abra la carpeta completa. No mezcle archivos de modelos. Adaptar descarta intervalos. Recalibre con grupos independientes nuevos y no reutilice observaciones retenidas.

### 5.4 Cálculo lento o controles bloqueados

Espere a Listo. Monte Carlo y benchmark pueden tardar más que una simulación. Para una práctica nueva reduzca muestras/segmentos cuando no haya un trabajo activo. El bloqueo evita cambios durante el cálculo.

### 5.5 Gráficas o campos incompletos

Amplíe la ventana, desplace el panel y pulse Home. Compruebe si existe resultado y si hubo agotamiento. Exporte una figura para ampliarla. Una banda vacía después del agotamiento no predice SOC.

### 5.6 El programa no inicia

Extraiga el ZIP completo y compruebe _internal. La entrega Windows x64 no tiene instalador ni firma digital. Desde fuentes, revise Python, Tkinter y dependencias. No sustituya el diagnóstico por cambios de seguridad del equipo.

### 5.7 Soporte y límites

Contacto: fjburgosf@gmail.com. Indique versión, revisión, YAML, entradas y error. La versión pasó 80 pruebas de regresión y 114 comprobaciones GUI en fuentes y 114 en el EXE con respuestas controladas de diálogos. No se certifican todos los estados ni precisión física real. La metodología conserva resultados desfavorables y límites históricos. Derechos: LICENSE.
