# Adaptación y evaluación causal

Después de entrenar CGPRA, una ruta nueva puede actualizar la calibración física
por RLS acotado y reconstruir los residuos del historial contra la física actualizada.
El aprendizaje usa la energía observada únicamente después de predecir esa ruta.
Cada grupo de ruta se consume una sola vez. Las rutas utilizadas para calibrar
intervalos no pueden reutilizarse para adaptar ni para una nueva calibración de
intervalos posterior a la adaptación.

```powershell
bikeenergylab adapt CARPETA_MODELO nuevas_rutas.csv --output resultados
bikeenergylab adapt CARPETA_MODELO nuevas_rutas.csv --calibration-dataset rutas_independientes.csv
bikeenergylab predict configs/flat.yaml --model CARPETA_ADAPTADA --point-only
```

La GUI ofrece adaptación y recalibración de intervalos por separado. Cada adaptación
invalida los intervalos conformales y las muestras empíricas de error previas. Se
pueden simular o predecir puntos. Para incertidumbre aprendida se requieren rutas
frescas independientes (al menos 19 para el intervalo conformal del 95%). El artefacto
guarda el historial, parámetros y covarianza secuencial. Si falla entrenamiento o
adaptación, el objeto original conserva su estado válido. La CLI guarda siempre
un artefacto nuevo y conserva el anterior.

`bikeenergylab prequential configs/adaptive_validation.yaml` ejecuta una comparación
controlada entre el mismo modelo inicial congelado y adaptado. En el generador,
Crr varía linealmente de 0.008 a 0.011, CdA=0.48 y el ruido declarado es
0.06 Wh/km. Se registran predicciones M1/M3/M4 **antes** de cada actualización,
datos, semillas, verdad sintética, métricas y modelos inicial/final. La prueba de
causalidad altera la última etiqueta y verifica que ninguna predicción previa
ni la predicción de esa última ruta haya cambiado.

La calibración adaptativa no observa SOC ni demuestra identificación universal.
RLS puede distribuir una discrepancia entre parámetros correlacionados. Comparar
energía y diagnósticos de identificabilidad además de parámetros. Este experimento
evalúa deriva sintética declarada. La eficacia con deriva real requiere telemetría.

Para sensores, `bikeenergylab telemetry datos.csv` valida calidad e integra potencia
terminal V·I por trapecios con tiempos en segundos, preservando paradas. Produce
`observations.csv` para calibración/aprendizaje y un informe de conversión. Los CSV
de ejemplo se etiquetan explícitamente como sintéticos.
