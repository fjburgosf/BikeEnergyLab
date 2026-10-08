# Distribución portátil Windows

La entrega de Windows x64 es `BikeEnergyLab-1.0.0-windows-x64.zip`. Extraerla
completa y abrir `BikeEnergyLab/BikeEnergyLab.exe`. No necesita una instalación
de Python ni conexión a Internet. Conservar la carpeta `_internal` junto al
ejecutable: contiene las bibliotecas, DLL, recursos Tk/Matplotlib y metadatos.

Se incluyen manuales, configuración, ejemplos, datasets sintéticos, licencia,
citación, versiones y avisos de dependencias. `SHA256SUMS.json` permite verificar
integridad de todos los archivos del paquete. No es una firma digital del editor.

La carpeta `docs/docx` contiene los tres documentos Word en español:
[manual de usuario](docx/Manual_de_usuario_BikeEnergyLab_1.0.0.docx),
[manual técnico](docx/Manual_tecnico_BikeEnergyLab_1.0.0.docx) y
[metodología científica](docx/Metodologia_cientifica_BikeEnergyLab_1.0.0.docx).
Incluyen ejemplos y tutorial, API y distribución, ecuaciones editables,
referencias y resultados de validación sintética. Se revisaron las 21 páginas
renderizadas por Microsoft Word antes de incorporarlos al paquete.

Desde PowerShell dentro de la carpeta extraída:

```powershell
.\BikeEnergyLab.exe --version
.\BikeEnergyLab.exe simulate configs/flat.yaml --output results
.\BikeEnergyLab.exe uncertainty configs/flat.yaml --output results
.\BikeEnergyLab.exe sensitivity configs/flat.yaml --method sobol --samples 256
.\BikeEnergyLab.exe telemetry datasets/telemetry_example.csv --output results
.\BikeEnergyLab.exe train datasets/synthetic_calibration.csv --output results
.\BikeEnergyLab.exe benchmark configs/benchmark.yaml --output results
.\BikeEnergyLab.exe prequential configs/adaptive_validation.yaml --output results
```

`docs/user_manual.md` explica los quince módulos, unidades, datos y exportación.
En Inicio, el menú **Ejemplos** ofrece nueve ejercicios ejecutables. El botón
**Tutorial** abre la guía integrada de ocho pasos. Ambos están disponibles en
ES/EN y no requieren los archivos Python externos ni conexión.
Después de **Cargar ejemplo**, **Simular** ejecuta su flujo completo. Estas son
las dos acciones del flujo de ejemplos.
Los archivos `.py` de `examples` son ejemplos de la API para una instalación Python.
Sus configuraciones también pueden ejecutarse con el programa portátil.

El ejecutable se verifica en este equipo con simulación, inferencia M1–M4,
incertidumbre aprendida y GUI ES/EN. El wheel se comprueba en un entorno Python
aislado, sin bibliotecas heredadas del sistema. El código fuente, lock y scripts
permiten repetir el proceso de build. No se promete igualdad binaria entre builds.

No incluye instalador ni firma de código. La verificación en otro equipo Windows
y la validación de precisión con bicicletas reales son evidencias adicionales
que no se sustituyen por estas pruebas de distribución.

La carpeta **Entregables** contiene únicamente cinco DOCX y dos ZIP, uno portátil
y otro de código fuente. Extraiga el ZIP portátil fuera de Entregables y abra
`BikeEnergyLab/BikeEnergyLab.exe`. Conserve su carpeta completa con las dependencias.
Los registros de revisión y los hashes de entrega se conservan por separado
en `results/delivery-1.0.0`. El ZIP de fuentes contiene el código, los documentos
y los scripts necesarios para reproducir la distribución.
