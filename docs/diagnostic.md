# Diagnóstico técnico inicial — 2026-10-01

Se inspeccionó `E:/software/BikeEnergyLab`, incluidos archivos ocultos y
subdirectorios. La carpeta estaba vacía.
No se encontraron fuentes, interfaces, scripts, datasets, modelos, documentación,
figuras, configuraciones, ejecutables, notebooks, pruebas ni resultados.
No existía software que pudiera ejecutarse. Esta constatación difiere de la
premisa de avances previos. No se eliminó ni reorganizó trabajo existente.

## Decisión de arquitectura

Paquete `src/bikeenergylab`, núcleo headless y adaptadores separados para CLI,
GUI Tk y figuras Matplotlib. NumPy/SciPy para física y calibración. Scikit-learn
para baselines y soporte estadístico. Pandas para tablas y PyYAML para configuración.
Los componentes físicos intercambian unidades SI. Los exports explicitan Wh/km.

Primero se verifica el recorrido Bike → Route → Physics → Energy → SOC → Range
→ Visualization → Export, seguido de calibración y comparación M1–M4 con
particiones por ruta. Se conserva la velocidad prescrita como un problema inverso
de dinámica y se informa déficit de potencia: no se declara una misión viable si
el motor y el ciclista no pueden sostener el perfil solicitado.

Los valores iniciales son supuestos editables, no mediciones. No existen datos
reales disponibles: los experimentos iniciales usan un generador sintético con
parámetros conocidos y discrepancia estructural explícita. Una comparación
sintética no demuestra superioridad en bicicletas reales ni novedad académica.

## Distribución

Se prepara API, CLI, GUI y build Windows. No se selecciona una licencia de cesión
de derechos sin una decisión de los autores. La distribución permanece reservada
hasta esa elección.
