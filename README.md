# España Outdoor Data Pipeline

Pipeline de ingestión, inventario, validación, deduplicación y preparación de datos geográficos para España Outdoor.

## Objetivo

Procesar grandes colecciones de GPX/KML y otros recursos geográficos sin modificar los archivos originales. El pipeline genera un catálogo local consultable y prepara datos para futuras fases de normalización, clasificación, exportación y publicación.

## Principios

- **Los originales nunca se modifican ni se borran.**
- **Los datos no forman parte del repositorio Git.**
- El catálogo y los informes generados localmente también quedan fuera de Git.
- El procesamiento debe ser reanudable.
- Los duplicados se marcan; no se eliminan automáticamente.
- La procedencia y licencia de los datos externos deben conservarse.
- La aplicación Android consume datos preparados; no ejecuta este pipeline.

## Arquitectura

```text
Fuentes / corpus local
        |
        v
    Scanner
        |
        +--> inventario de archivos
        +--> hashes
        +--> metadatos básicos
        +--> estado de lectura
        |
        v
   SQLite catalog
        |
        +--> validación GPX/KML
        +--> deduplicación
        +--> clasificación
        +--> exportación
        |
        v
Datos de producción -> R2 / servicios / aplicación
```

## Estructura

```text
src/                    código del pipeline
scripts/                puntos de entrada y utilidades
tests/                  pruebas automatizadas
config/                 configuración versionada
docs/                   documentación
schemas/                esquemas de datos
```

Los directorios de datos de trabajo (`data/`, `reports/`, `processed/`, etc.) están excluidos mediante `.gitignore`.

## Primer componente: scanner

El scanner de la versión inicial es deliberadamente conservador. Recorre un directorio indicado por el usuario y registra en SQLite:

- ruta y nombre
- extensión
- tamaño
- fechas del sistema de archivos
- SHA-256
- estado del escaneo

Primero se prioriza la integridad del inventario. El análisis profundo de geometría, deduplicación geométrica y clasificación semántica se incorporará en fases posteriores.

## Uso previsto

```powershell
python -m espana_outdoors_pipeline.scanner --root "F:\España Outdoor Maps"
```

La ruta de datos es externa al repositorio. No es necesario copiar los datos al proyecto.

## Licencia

El código de este repositorio se distribuye bajo Apache License 2.0. Consulta `LICENSE`.

Los datos externos procesados por este software **no están cubiertos automáticamente por esta licencia**. Cada conjunto de datos mantiene sus propias condiciones de uso. Consulta `DATA-LICENSING.md`.
