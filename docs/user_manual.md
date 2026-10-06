# Manual de usuario

## Empezar con ejemplos y tutorial

Desde **Inicio** o el botón **Ejemplos** de la barra superior, seleccione un caso
en el menú desplegable. Cada ejemplo explica sus parámetros y qué observar.
**Cargar ejemplo** prepara la configuración para inspeccionarla o modificarla;
después, **Simular** ejecuta el procedimiento del ejemplo activo con los parámetros
actuales. El flujo tiene dos acciones: **Cargar ejemplo** y **Simular**.
Cargar reemplaza los parámetros en pantalla, el último resultado y el modelo
híbrido activo. Los archivos previamente guardados se conservan.

| Ejemplo | Qué permite practicar |
| --- | --- |
| 01 · Ruta plana | Primer cálculo: 3 km, 6 m/s y 50 W humanos |
| 02 · Subida del 3% | Demanda gravitacional a 5 m/s |
| 03 · Viento frontal | Comparar −3 m/s con la ruta plana |
| 04 · Mayor aporte humano | Comparar 120 W con 50 W en pedales |
| 05 · Ambiente frío | Densidad del aire a 0 °C; sin curva térmica de batería |
| 06 · Calibración sintética | Recuperar Crr = 0.008 y CdA = 0.48 m² con 40 rutas |
| 07 · Viento incierto y autonomía | 30 muestras; dispersión y horizonte de 80 km |
| 08 · Modelo híbrido CGPRA | 60 rutas de entrenamiento y 25 de intervalos independientes |
| 09 · ¿Alcanza la batería? | 26 km, SOC inicial 38% y reserva 15% |

El programa muestra **Ejemplo activo**. Cambiar la selección del desplegable no
carga un caso: hay que pulsar **Cargar ejemplo** y después **Simular**.
En los ejemplos 01–05, Simular hace el cálculo físico; en el 06 ajusta parámetros;
en el 07 y el 09 calcula incertidumbre y misión. En el 08 entrena e infiere la
primera vez y reutiliza el modelo en las siguientes simulaciones. El modelo puede
guardarse desde **Modelo híbrido**. Abrir otro YAML inicia un cálculo general,
sin un ejemplo activo. Todos los datos de práctica son sintéticos.

Pulse **Tutorial** o **Iniciar tutorial guiado** para abrir la guía integrada.
Sus ocho pasos presentan la configuración, parámetros, ruta, simulación,
lectura de resultados, incertidumbre, exportación y siguientes ejercicios.
Use el botón de acción de cada paso para practicar y **Anterior / Siguiente**
para avanzar. El panel guía permanece visible mientras explora las secciones.
Puede cerrarlo sin cerrar el programa y reiniciarlo desde la barra superior.
Cambiar ES/EN mantiene el paso y la selección del ejemplo. Funciona sin conexión.

## Flujo de trabajo completo

1. **Abrir:** ejecutar `bikeenergylab gui`, el ejecutable Windows o la CLI.
   El selector ES/EN cambia la interfaz y las ayudas. Los nombres técnicos de
   columnas y parámetros son estables en ambos idiomas.
2. **Bicicleta:** masas, CdA, Crr, radio y eficiencia. Los valores iniciales son
   supuestos; reemplazarlos por mediciones. Superficies y curvas se editan en YAML.
3. **Ciclista:** masa y potencia en pedales. Usar constante, perfil en CSV o modo
   dependiente de cadencia/pendiente/fatiga con coeficientes explícitos.
4. **Motor:** eficiencia constante/mapa y límites. Asistencia demand sigue la
   demanda; proportional sigue el aporte humano. La regeneración solo se activa
   con hardware capaz. Los límites no representan automáticamente normativas.
5. **Batería:** Wh nominales, fracción efectiva, SOC inicial, reserva y SOC máximo.
   `ecm` requiere capacidad Ah, OCV y resistencias de la batería concreta.
   Coeficientes térmicos ausentes significan ausencia de ese efecto en el modelo.
6. **Ruta:** crear un perfil manual o importar CSV/GPX con elevación. CSV usa
   intervalos length_m/dt_s/speed_mps/grade. GPX con tiempos deriva velocidad;
   sin tiempos usa la velocidad indicada. El filtro mediano se registra.
   Pulsar **Visualizar ruta** para ver elevación, pendiente, velocidad y superficie.
   Las paradas GPX con tiempos se conservan; segmentos discontinuos requieren
   preparación explícita. Crear ruta manual aplica los tres campos editados.
7. **Ambiente:** temperatura, viento (negativo frontal), presión/densidad.
   Columnas temporales de ruta tienen prioridad sobre constantes.
8. **Simular:** configurar timestep y auxiliares; pulsar Simular. El cálculo
   corre en background. Revisar energía, SOC, distancia y `feasible`.
   Los controles de edición se bloquean durante el cálculo. Los formularios
   largos permiten desplazamiento vertical. Resultados ofrece pestañas y barra
   de zoom/guardado para explorar gráficas y un detalle JSON completo.
   Si falta potencia, el perfil solicitado requiere modificar velocidad,
   asistencia o aporte humano. Un perfil incompleto no demuestra que pueda
   completarse la misión al ritmo prescrito.
9. **Interpretar consumo:** Wh/km es energía eléctrica neta por distancia recorrida.
   La descomposición conserva los signos e incluye pérdidas y frenado. El balance
   debe tener error numérico cercano a cero. Descensos no implican regeneración
   cuando está desactivada.
10. **Calibrar:** cargar CSV de rutas independientes con energía observada total.
    Inspeccionar reporte de calidad e identificabilidad. Crr/CdA necesitan variación
    de velocidad y condiciones; repetir una ruta a velocidad fija puede confundirse.
    Un ajuste preciso no demuestra parámetros físicamente identificados.
    **Convertir CSV de sensores** produce observaciones exportables a partir de
    tiempo/distancia/voltaje/corriente, conservando un informe de calidad.
11. **Modelo híbrido:** entrenar CGPRA con al menos 40 rutas independientes para
    separar entrenamiento e intervalos. La demostración sintética está rotulada.
    Las siguientes simulaciones muestran predicción, alpha, soporte OOD e intervalo.
    Alpha bajo indica que domina la física calibrada, sin asegurar exactitud.
    Guardar modelo CGPRA crea una carpeta nueva con CSV/JSON y mapas necesarios.
    Abrir modelo CGPRA reconstruye y verifica el ajuste. Conservar la carpeta completa.
    **Adaptar** usa rutas nuevas y descarta intervalos previos. **Recalibrar intervalos**
    requiere rutas independientes frescas; véase [adaptación](adaptive_workflow.md).
12. **Incertidumbre:** editar las distribuciones en YAML y Aplicar YAML. Misión /
    autonomía devuelve simulaciones Monte Carlo físicas y probabilidad de éxito
    según la reserva. Revisar el horizonte y fracción de autonomía censurada.
    Con un CGPRA con calibración independiente vigente, también muestra energía
    predictiva de la ruta completa. `energy_budget_probability` evalúa energía
    disponible; `mission_probability` conserva la simulación física. Revisar casos
    no identificados, soporte OOD y supuestos de transferencia de errores en el
    [flujo predictivo](predictive_workflow.md).
    Las bandas de SOC/energía son físicas y condicionales a llegar a cada punto;
    inspeccionar `n_reached` cuando existen rutas agotadas. No extrapolan su SOC.
13. **Misión con SOC 38%:** configurar initial_soc=0.38, importar ruta de 26 km,
    reserve_soc=0.15 y distribuciones justificadas. La probabilidad exige ruta
    completa, potencia suficiente y SOC final sobre la reserva.
14. **Experimentos:** ejecutar benchmark ID/OOD o EXP-01–15 desde GUI/CLI y
    seleccionar sensibilidad OAT/Spearman/Morris/Sobol. Leer resultados positivos
    y negativos, coverage e interval width;
    no comparar MAE entre datasets con unidades o particiones incompatibles.
15. **Exportar:** escoger carpeta para el último resultado. La carpeta EXP contiene
    configuración, datos, metadatos, parámetros, tablas, figuras y logs. Conservar
    estos artefactos juntos para repetir el experimento. Configuraciones avanzadas
    se guardan con Guardar YAML; rutas importadas se copian en el export.

## Comandos útiles

```powershell
bikeenergylab simulate configs/flat.yaml
bikeenergylab uncertainty configs/flat.yaml
bikeenergylab calibrate datasets/synthetic_calibration.csv
bikeenergylab benchmark configs/benchmark.yaml
bikeenergylab experiments configs/benchmark.yaml
bikeenergylab quality datasets/telemetry_example.csv
bikeenergylab train datasets/synthetic_calibration.csv --seed 42
bikeenergylab predictive-validation configs/predictive_validation.yaml
bikeenergylab telemetry datasets/telemetry_example.csv
bikeenergylab sensitivity configs/flat.yaml --method morris --samples 16
bikeenergylab prequential configs/adaptive_validation.yaml
```

`--output` elige carpeta. No se requieren mapas, cuentas, APIs ni conexión a
internet para las simulaciones; instalar dependencias inicialmente sí puede
requerir conexión. Los errores de unidades y configuración deben resolverse de
forma explícita, sin modificar silenciosamente las mediciones.
