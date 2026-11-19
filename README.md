# Proyecto 2 — RIT S2 2026: PaleoBusca, el índice

Indexación de la colección del arañador PaleoBusca (proyecto 1) con dos implementaciones:
un índice binario propio y uno de Apache Lucene, ambos con las mismas políticas de normalización.

## Estructura

| Carpeta | Contenido |
|---|---|
| `normalizacion/` | Políticas de normalización compartidas por los dos indexadores |
| `normalizacion/ESPECIFICACION.md` | **Qué se normaliza, en qué orden y por qué** (fuente para el documento) |
| `normalizacion/perfiles/` | Los 3 perfiles (`p1_base`, `p2_stemming`, `p3_completo`) en formato `.conf` |
| `normalizacion/recursos/` | Stopwords, tesauro, expresiones de varias palabras, plegado, lemas |
| `normalizacion/python/paleonorm` | Normalizador para el indexador manual |
| `normalizacion/java` | `PaleoAnalyzer` para Lucene 9.12.1 (Gradle) |
| `normalizacion/pruebas/golden.tsv` | Casos que ambas implementaciones deben cumplir |
| `normalizacion/herramientas/` | Generación de lemas y golden, verificación Python ↔ Lucene |

## Requisitos

- Python 3.11+ (`pip install -r normalizacion/python/requirements.txt`)
- Java 21 (Gradle se descarga solo con `normalizacion/java/gradlew`)

## Bitácora

`BITACORA.csv` registra lo que hace cada persona del equipo. **Cada vez que hagan un cambio, agreguen
una fila al final** (en el mismo commit), sin borrar las anteriores:

| Columna | Qué poner |
|---|---|
| `fecha` | `AAAA-MM-DD` |
| `autor` | su usuario de GitHub |
| `area` | `Normalización`, `Indexador manual`, `Indexador Lucene`, `Documento` o `General` |
| `tipo` | `Creación`, `Cambio`, `Corrección`, `Decisión`, `Pruebas` o `Pendiente` |
| `descripcion` | qué se hizo y por qué |
| `archivos` | rutas afectadas, separadas por `;` |
| `estado` | `Hecho` o `Pendiente` (cuando terminen un pendiente, agreguen una fila nueva que lo marque `Hecho`) |

Se puede editar en Excel, LibreOffice o en texto plano. Si un texto lleva comas, va entre comillas dobles.
