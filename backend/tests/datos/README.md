# Datos de prueba

- `custom_result.json`: salida **real** de BDA (custom output) para `cv-02-data-science.pdf`, de una prueba en la consola el 19 oct con una versión anterior del blueprint (sin `idiomas_estimados`). El ID de cuenta se reemplazó por `123456789012`. La hoja de vida es una plantilla con datos de ejemplo.
- `job_metadata.json` y `standard_result.json`: **ilustrativos**, escritos a mano según la forma documentada. Reemplázalos por los que BDA deje en `ResultadosBdaBucket/bda/{documentoId}/` después del primer despliegue y vuelve a correr `uv run pytest`.
