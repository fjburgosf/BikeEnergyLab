# Instrucciones de trabajo de BikeEnergyLab

## Documentación Word obligatoria en cada actualización

El usuario exige mantener los DOCX actualizados cada vez que se actualice el
software. Esta regla forma parte de la entrega, aunque el usuario no la repita.
Una actualización del software no está terminada hasta completar también la
actualización y revisión de sus tres documentos Word.

- Manual de usuario: `docs/docx/Manual_de_usuario_BikeEnergyLab_<version>.docx`.
- Manual técnico: `docs/docx/Manual_tecnico_BikeEnergyLab_<version>.docx`.
- Metodología científica:
  `docs/docx/Metodologia_cientifica_BikeEnergyLab_<version>.docx`.

En cada cambio, revisar los tres documentos y actualizar el contenido que
corresponda: interfaz, ejemplos, tutorial, configuración, API, comandos,
instalación, algoritmos, ecuaciones, resultados, pruebas y límites. Incluso si
una sección mantiene su contenido, comprobar que siga describiendo el software
actual. Los documentos deben identificar la versión y la revisión de la entrega.
No basta con actualizar Markdown y dejar los DOCX anteriores.

## Proceso de actualización y entrega

1. Actualizar las fuentes de los documentos junto con el cambio de software:
   `docs/user_manual.md`, `docs/docx_sources/manual_tecnico_es.md` y
   `docs/docx_sources/metodologia_es.md`. Mantener también los manuales y
   referencias Markdown relacionados cuando corresponda.
2. Actualizar versión, fecha, ejemplos, pruebas y resultados en el generador
   `scripts/create_docx_manuals.py` y sus fuentes cuando cambien. La versión se
   comprueba contra `pyproject.toml`; no conservar metadatos antiguos.
3. Aplicar la habilidad documents disponible, generar los tres DOCX con su
   runtime de autoría y conservar las ecuaciones como objetos editables de Word.
4. Actualizar índices y numeración, renderizar y revisar visualmente todas las
   páginas finales. En este equipo se dispone de `scripts/render_docx_word.ps1`
   y `scripts/render_docx_pages.py`. Una modificación posterior del DOCX requiere
   repetir su renderizado y revisión; no usar imágenes de una revisión anterior.
5. Actualizar `results/documents-verification-<version>.json` con los hashes
   SHA256 de los DOCX finales, páginas y revisión realmente realizada. Mantener
   coherentes los enlaces y descripciones de `docs/docx/README.md`, README y
   documentación de distribución.
6. Regenerar los paquetes de fuentes y portátil con `scripts/build_package.py`
   y `scripts/package_windows.py`. Incluir los tres DOCX finales y comprobar que
   sus hashes dentro de los paquetes coincidan con los documentos revisados.
   Los PDF e imágenes de QA son internos y no sustituyen la entrega DOCX.
7. Actualizar el registro de la entrega y verificar su integridad. Usar el
   proceso de validación apropiado al alcance del cambio; `record_ui_release.py`
   solo admite cambios de interfaz/documentación con núcleo científico intacto.
   No declarar la actualización lista mientras falten los DOCX sincronizados.

## Fidelidad científica

Documentar el comportamiento y la evidencia reales de la versión. Conservar la
identidad y los límites de resultados históricos, incluidos los desfavorables.
No presentar datos sintéticos como mediciones reales ni pruebas de software
como validación de precisión física. Las correcciones de interfaz no justifican
atribuir nuevos resultados a protocolos científicos que no se hayan ejecutado.
