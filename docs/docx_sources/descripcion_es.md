# Descripción del software BikeEnergyLab

## 1. Información general del producto

| Elemento | Descripción |
| --- | --- |
| Nombre y versión | BikeEnergyLab 1.0.0 |
| Tipo de producto | Framework científico de modelado energético de bicicletas eléctricas |
| Autores | Francisco Javier Burgos Flórez y Juan Guillermo Popayán Hernández |
| Año y revisión | 2026; plantillas e interfaz ilustrada del 6 de octubre |
| Contacto | fjburgosf@gmail.com |
| Lenguaje y distribución | Python 3.11 o superior; aplicación portátil Windows x64 |
| Repositorio | https://github.com/fjburgosf/BikeEnergyLab |
| Estado | Funcional y verificado mediante pruebas de software y datos sintéticos |
| Derechos | Los establecidos en LICENSE; no se presume una licencia abierta |

## 2. Descripción general del software

BikeEnergyLab calcula la demanda energética necesaria para seguir una ruta con velocidad prescrita. El usuario define la bicicleta, el ciclista, la asistencia del motor, la batería y las condiciones ambientales. El software integra fuerzas longitudinales, pérdidas de transmisión y motor, auxiliares y regeneración opcional, y registra el estado de batería, la demanda no satisfecha y la finalización de la ruta.

La física explícita puede calibrarse con energías observadas de rutas completas. El modelo CGPRA añade una corrección residual ponderada por una compuerta de confianza. El análisis Monte Carlo estudia energía, autonomía y misión bajo distribuciones configuradas; la sensibilidad permite explorar la influencia de parámetros. La GUI, la CLI y la API comparten los mismos componentes numéricos.

### 2.1 Requisitos de hardware y software

El ejecutable requiere Windows x64 y conservar su carpeta _internal. Funciona sin instalar Python y sin conexión para simular los ejemplos incluidos. La ejecución desde fuentes requiere Python 3.11 o superior y las dependencias de pyproject.toml. Tkinter proporciona la GUI. No se requiere una bicicleta conectada, microcontrolador, puerto serial ni GPU.

### 2.2 Justificación de los requisitos

NumPy y SciPy proporcionan cálculo e identificación; pandas procesa datos; scikit-learn implementa regresión y aprendizaje residual; Matplotlib genera figuras; PyYAML conserva configuraciones. La distribución onedir incluye estas dependencias, sus licencias y los datos de SciPy necesarios para Sobol. El costo de cálculo crece con las rutas, segmentos, muestras y protocolos seleccionados; no se atribuye un tiempo universal de ejecución.

## 3. Objetivos y área de aplicación

### 3.1 Objetivo general

Ofrecer un entorno reproducible para estudiar el consumo de energía y la autonomía de bicicletas eléctricas, calibrar supuestos físicos y evaluar cuándo una corrección basada en datos mejora o empeora una predicción.

### 3.2 Área de aplicación

Se dirige a investigación, docencia y análisis de movilidad eléctrica. Permite comparar rutas, aporte humano, viento y temperatura, diseñar experimentos sintéticos y preparar flujos de datos observados. Su aplicación a decisiones de operación real requiere caracterización de la bicicleta y validación independiente.

## 4. Funcionalidades principales

La simulación física produce series de potencia, energía y SOC, balances e indicadores de factibilidad. La calibración ajusta parámetros acotados y ofrece diagnósticos de identificabilidad. El aprendizaje compara M1 físico, M2 basado en datos, M3 residual fijo y M4 CGPRA, con rutas independientes para entrenamiento, intervalos y prueba.

Se ofrecen importación CSV/GPX, conversión de telemetría, adaptación causal, recalibración de intervalos, Monte Carlo de misión y autonomía, sensibilidad OAT/Spearman/Morris/Sobol, benchmark ID/OOD y suite EXP 01 a 15. Los nueve ejemplos y la guía de ocho pasos permiten practicar sin archivos externos. Los resultados se exportan con configuración, datos y procedencia.

## 5. Adaptabilidad extensibilidad y mantenibilidad

La configuración utiliza dataclasses y YAML validado. Los módulos separan rutas, física, motor, batería, calibración, modelos residuales, incertidumbre y presentación. Nuevos mapas o curvas deben conservar las unidades, registrar sus límites y aportar pruebas apropiadas. La API permite reutilizar el núcleo sin abrir la interfaz gráfica.

Los scripts de distribución y generación documental forman parte de las fuentes. Las plantillas de estilo conservadas y las capturas permiten reproducir los documentos. La documentación, los paquetes y sus hashes deben actualizarse conjuntamente después de cada cambio.

## 6. Robustez desempeño y consistencia

### 6.1 Robustez

La configuración rechaza secciones y campos desconocidos, verifica límites y conserva los errores de entrada. Las operaciones de entrenamiento y adaptación son transaccionales. La GUI realiza cálculos con un trabajador y actualiza los widgets desde el hilo principal; bloquea los controles mientras calcula. No produce resultados exitosos cuando una tarea falla.

### 6.2 Desempeño

La versión pasó 80 pruebas de regresión y 114 comprobaciones ampliadas de interfaz tanto en fuentes como en el ejecutable. El wheel aislado y el EXE coincidieron en predicciones con tolerancia de 1e-8. Estas comprobaciones verifican implementación y empaquetado, y no establecen tiempos de respuesta ni exactitud física universal.

### 6.3 Consistencia y reproducibilidad

Cada ejecución conserva semillas, configuración, dependencias y hashes. Las exportaciones crean directorios nuevos. Los modelos reutilizables se almacenan como CSV y JSON, se reconstruyen y verifican mediante predicciones de referencia. Debe conservarse cada carpeta completa.

## 7. Interfaz y usabilidad

Quince secciones organizan el flujo desde Inicio hasta Exportar. El menú de ejemplos distingue la selección del caso activo: Cargar ejemplo prepara el caso y Simular ejecuta su procedimiento. La guía integrada explica ocho pasos y conserva su posición al cambiar español/inglés. El manual de usuario contiene capturas de los paneles y resultados, explica todos los botones y desarrolla los nueve ejercicios.

## 8. Integridad y seguridad de la información

La aplicación es local y no implementa cuentas ni acceso remoto. Los archivos se guardan en formatos legibles sin cifrado. Los hashes comprueban identidad e integridad, pero no constituyen una firma de autenticidad. El usuario controla permisos, copias y divulgación de sus datos. Los ejemplos de entrega son sintéticos.

El importador valida formatos y coherencia. Los mapas y rutas utilizados se copian en la exportación. El modelo se reconstruye desde datos declarados y verifica replay; no necesita ejecutar un archivo pickle arbitrario. El ejecutable de esta entrega no tiene firma digital.

## 9. Portabilidad y compatibilidad

### 9.1 Plataformas compatibles

La entrega comprobada incluye Windows x64 y ejecución Python en este equipo. Las dependencias principales son portables, pero no se declara validación de la GUI ni de paquetes en Linux, macOS u otra máquina Windows.

### 9.2 Dependencias relevantes

Los requisitos mínimos están en pyproject.toml y las versiones usadas en requirements-lock.txt. El paquete portátil incluye intérprete, recursos Tk/Matplotlib, DLL, metadatos, datos de SciPy y avisos de terceros. _internal debe permanecer junto al EXE.

### 9.3 Portabilidad de resultados

CSV, YAML, JSON y figuras permiten analizar resultados sin depender de la sesión abierta. La portabilidad requiere conservar mapas, rutas y metadatos copiados. El ZIP de fuentes incluye configuración, pruebas, scripts, documentos y componentes de estilo.

## 10. Documentación y soporte técnico

La entrega incluye manual de usuario ilustrado, manual técnico, metodología científica, descripción del software y título/funciones en Word. El código y la documentación están en https://github.com/fjburgosf/BikeEnergyLab. Entregables reúne estos cinco DOCX, las fuentes ZIP, el EXE con sus dependencias y el paquete portátil.

El contacto del proyecto es fjburgosf@gmail.com. Al informar un problema, conservar la versión, YAML, datos, mensaje de error y carpeta de exportación. Revisar antes la sección de solución de problemas del manual.

## 11. Pruebas validación y desempeño

La evidencia de software comprueba los botones mediante widgets reales de Tk y respuestas controladas de diálogos; cubre archivos, ejemplos, modelos, tutorial, sensibilidad, benchmark, EXP 01 a 15 y exportaciones. No certifica el aspecto de todos los diálogos nativos ni todos los estados posibles. Los hashes de los documentos finales y los paquetes se registran en results.

La evidencia científica histórica conserva su identidad y resultados: M3 tuvo menor CRPS que M4 en el protocolo ID y M4 perdió cobertura en escenarios térmicos/combinados OOD. En deriva sintética, M1 adaptativo obtuvo el menor MAE. Estos hallazgos se explican en la metodología; no se sustituyen por resultados favorables ni por las pruebas de GUI.

## 12. Impacto y utilización

### 12.1 Docencia

Los ejercicios permiten relacionar fuerzas, potencia, batería y supuestos con resultados visibles. La guía y los manuales reducen los pasos necesarios para comenzar una práctica.

### 12.2 Investigación

Los protocolos permiten comparar modelos bajo datos separados, cambios de distribución y adaptación causal. La utilidad científica depende de la pregunta, los datos y la evidencia obtenida.

### 12.3 Extensión y usuarios

Investigadores, estudiantes y analistas pueden preparar escenarios y flujos de observación. No se documentan aquí cifras de adopción, cursos realizados, usuarios externos o validaciones de campo.

## 13. Contribución al estado del arte

### 13.1 Problema abordado

El consumo depende de parámetros físicos, condiciones operativas y errores del modelo. Una corrección residual puede mejorar una predicción en un dominio y fallar bajo cambios de distribución.

### 13.2 Antecedentes y alcance

La formulación utiliza modelado longitudinal del ciclismo, circuitos equivalentes de batería, aprendizaje residual, soporte OOD e intervalos conformales. Las referencias se conservan en docs/references.md y en la metodología científica. Sustentan conceptos y no avalan los valores predeterminados de esta implementación.

### 13.3 Límites y contribución propuesta

CGPRA es una formulación provisional evaluable. La integración de física, corrección ponderada, adaptación y protocolos permite estudiar sus límites; no demuestra por sí misma originalidad académica ni superioridad universal. Faltan datos reales independientes y una revisión sistemática de trabajos previos.

## 14. Aportes y autoría

Los autores identificados del software son Francisco Javier Burgos Flórez y Juan Guillermo Popayán Hernández. Esta entrega comprende el núcleo científico, interfaz, ejemplos, tutorial, pruebas, distribución y documentación. No se asignan contribuciones individuales adicionales sin una declaración de los autores. Conservar CITATION.cff y las condiciones de LICENSE al citar o distribuir.

## Referencias

Las referencias bibliográficas verificadas del proyecto se mantienen en docs/references.md y se desarrollan en Metodología científica de BikeEnergyLab. Las fuentes de evidencia conservan los protocolos del 4 de octubre de 2026 y su identidad histórica. La revisión documental del 6 de octubre no constituye una nueva validación física.

{{SOURCE}}
