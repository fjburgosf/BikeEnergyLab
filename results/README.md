# Evidencia incluida con BikeEnergyLab 1.0.0

Los ZIP de fuentes y Windows incluyen una selección verificable de resultados
bajo este directorio. evidence-inventory-1.0.0.json enumera rutas y SHA256.
La versión y los cuatro DOCX definitivos se revisaron el 8 de octubre de 2026.

- build_logs/tests-v1.0.0.log conserva la ejecución histórica de 80 pruebas.
  build_logs/tests-audit-v1.0.0.log conserva la repetición completa del 8 de
  octubre, sin la caché anterior y con una carpeta temporal aislada.
- build_logs/gui-buttons-source-v1.0.0.log y
  build_logs/gui-buttons-windows-v1.0.0.log respaldan 114 controles por entorno.
  Los reportes individuales están en gui-button-verification-1.0.0.
  build_logs/windows-audit-v1.0.0.log registra el arranque y smoke test del
  ejecutable repetidos el 8 de octubre.
- release-1.0.0/acceptance.json y
  distribution-verification-1.0.0/verification.json registran el alcance de las
  pruebas, la identidad de fuentes y la comparación wheel/EXE.
- Los CSV predictive/.../aggregate.csv y prequential/.../metrics.csv
  conservan los resultados sintéticos resumidos. Sus protocolos, metadatos,
  índices de suite y ejemplos se incluyen. docs/validation_data conserva
  copias trazadas de las dos tablas numéricas usadas en el manual técnico.
- documents-verification-1.0.0.json registra los cuatro DOCX, sus hashes y
  cada página revisada. Las imágenes de las capturas y su manifiesto están
  bajo docs/images/gui-1.0.0.

Los expedientes crudos completos de protocolos, predicciones por ruta, imágenes
de QA y el historial de builds permanecen en el espacio de desarrollo, bajo
results/release-1.0.0 y results/history. No forman parte de estos ZIP.
results/release_verification.json y results/delivery-1.0.0 del espacio de
desarrollo registran los hashes finales de paquetes; se excluyen para evitar
que un ZIP contenga su propio hash. El inventario de este directorio y los
SHA256 de los seis archivos de Entregables permiten verificar ambas capas.

Las prácticas y protocolos son sintéticos. Las pruebas de software comprueban
implementación y distribución, no precisión física en bicicletas reales.
