# Contrato de las plantillas de BikeEnergyLab

Referencias originales inalteradas en D:/Primbiolab/Registro de software/IPFramework.
catalog.json conserva sus rutas, SHA256 y el inventario de cada parte del paquete.
Las copias de lectura y los renders están en build/template-reference. Se revisaron
las 24 páginas de descripción, 26 del manual de usuario, 32 del técnico y una de
título y funciones. Todas las páginas se inspeccionaron en hojas a resolución
nativa de 100 dpi, sin reducir sus imágenes.

## Sistema de páginas y componentes

Los cuatro documentos usan papel carta de 8.5 por 11 pulgadas, orientación vertical.
Los manuales usan márgenes de una pulgada y distancias de encabezado/pie de media
pulgada. El manual de usuario tiene siete secciones: portada, contenido y cinco
capítulos. El técnico tiene once: portada, contenido y nueve capítulos. La metodología se integra en las secciones del manual técnico, conservando
sus nueve capítulos y las once secciones originales de la plantilla.
Descripción y título/funciones mantienen una sección. Las medidas exactas de cada
sección permanecen en los sectPr originales de los maestros.

La portada de los manuales tiene título de 32 puntos, subtítulo de 18 puntos,
separador azul, introducción en cursiva y tabla de metadatos con primera columna
azul clara. El cuerpo utiliza Calibri 11, justificación, títulos negros de 18 y
14 puntos, encabezado en cursiva de 9 puntos y línea azul. La descripción utiliza
Calibri 10.5, títulos de primer nivel de 16 puntos azul 1F3864 y segundo nivel de
13 puntos verde 0F6E6E. Portada de 28 puntos y subtítulo de 17. Las tablas de la
descripción usan encabezados azules y bordes finos. Los manuales usan sus tablas
originales sobrias. Se clonan los componentes, incluyendo pPr, rPr, tblPr y tcPr.
Los archivos styles.xml, numbering.xml, fontTable.xml y los temas son autoridad de
diseño y se conservan. Se permite añadir el estilo Code para fragmentos técnicos.

## Mapa de sustitución

- word/document.xml: todo el contenido anterior se sustituye. Se reutilizan
  los patrones de portada, tabla de metadatos, encabezados, cuerpo, listas,
  tablas y secciones. La tabla de contenido se regenera como campo Word.
- word/header*.xml: sustituir el nombre del producto y el tipo de documento.
  preservar tipografía, alineación y separador. Las portadas y contenidos
  mantienen sus encabezados vacíos.
- Imágenes anteriores: retirar y sustituir por capturas propias de BikeEnergyLab.
  Figuras de 6.5 pulgadas de ancho, leyendas numeradas y texto alternativo.
- Hipervínculos anteriores y propiedades: retirar. Usar los autores reales,
  contacto fjburgosf@gmail.com.
- Título y funciones: conservar el patrón compacto de dos párrafos, sin portada
  adicional ni tabla de contenido. Incorporar versión, revisión y contacto en
  esos párrafos.

Los maestros .template son copias de los paquetes originales con los contenidos
anteriores, imágenes e hipervínculos retirados. Conservan estilos, geometría,
numeración y componentes vacíos. No se usa Document() ni un diseño genérico.

## Organización y fidelidad

El manual de usuario conserva introducción, descripción del sistema, acceso,
uso y solución de problemas. Uso incluye quince paneles, todos los botones,
el tutorial y nueve ejemplos con condiciones, pasos y resultados propios.
El técnico conserva introducción, arquitectura, componentes, adquisición/datos,
operación, algoritmos, restricciones, despliegue y glosario. La descripción
conserva sus catorce capítulos y referencias, con contenido de BikeEnergyLab.
El manual técnico integra la metodología con sus ecuaciones editables y
evidencia histórica en introducción, componentes, algoritmos, restricciones
y referencias. La descripción incluye un resumen de su fundamento científico.

Se permite sustituir títulos específicos del producto anterior, corregir la
numeración de apartados y ampliar las ranuras para cubrir el programa actual.
No se transfieren afiliaciones, experimentos, resultados, autores ni afirmaciones
del producto anterior. Se mantienen los límites científicos de BikeEnergyLab.

Antes de entregar se comparan los estilos y las medidas con los maestros,
se actualizan campos con Word, se renderizan e inspeccionan todas las páginas
finales y se guardan sus hashes. Cada corrección exige render y revisión nuevos.

## Revisión editorial del 7 de octubre de 2026

La instrucción del usuario autoriza retirar la fila de ubicación del código
de las portadas y la tabla descriptiva, además de simplificar la puntuación.
Los estilos, las secciones, las capturas y las ecuaciones se conservan.

## Revisión de entrega del 8 de octubre de 2026

Se actualizan las instrucciones de distribución y la revisión de los cinco
Word. Entregables conserva únicamente cinco DOCX y dos ZIP. Las plantillas,
las capturas y las ecuaciones mantienen su sistema de diseño.

## Integración documental solicitada el 8 de octubre de 2026

Se entregan cuatro Word. La metodología completa se integra en el manual técnico
y su resumen en la descripción. No se genera un documento independiente.
Se conservan las 26 ecuaciones y toda la evidencia científica histórica.
