# PaleoBusca — Especificación de normalización

Este documento define **qué transformaciones se aplican al texto antes de indexarlo**, en qué orden y
por qué. Es el contrato común de los dos indexadores del proyecto 2:

- el **indexador manual** (archivo binario propio) usa el paquete Python `python/paleonorm`;
- el **indexador de Apache Lucene** usa `java/` → `PaleoAnalyzer`.

Las dos implementaciones leen **los mismos archivos** (`perfiles/*.conf` y `recursos/*`) y se
comprueban contra **los mismos casos** (`pruebas/golden.tsv`). Así se cumple el requisito de la
rúbrica: *"[Lucene] debe implementar las mismas estrategias de normalización que la implementación propia"*.

---

## 1. Punto de partida: la colección

Datos del proyecto 1 (arañador PaleoBusca):

| Característica | Valor | Consecuencia para la normalización |
|---|---|---|
| Idioma | Inglés (todas las semillas) | Stopwords, stemmer y lemas **del inglés** |
| Tamaño | 29 406 documentos, 0,343 GB, 49,6 M palabras | La normalización debe ser rápida (prioridad 2 del enunciado) |
| Vocabulario sin normalizar | 460 523 formas | La cola larga de Zipf es donde se gana tamaño de índice (prioridad 1) |
| Tema | Paleontología: géneros, binomiales, eras, siglas (K-Pg) | Proteger nombres de género, unir binomiales, tesauro propio |
| Fuentes | NHM, BBC, BGS (Reino Unido) y NPS, UCMP (EE. UU.) | Variantes ortográficas *palaeontology/paleontology*, *colour/color* |
| PDF | 4,7 % de los documentos y 29 % del texto | Ligaduras (ﬁ, ﬂ) y palabras partidas con guion al final de línea |
| Formato | `datos/repo/<dominio>/<nnnnn>/<id>.txt` + `datos/arana.db` (SQLite) | Los indexadores leen el `.txt` y toman `id`/`titulo`/`url` de la BD |

## 2. Pipeline

Se divide en una **etapa de texto** (pasos 1–10, transforma el documento completo como cadena) y una
**etapa de términos** (pasos 11–16, trabaja token por token). El orden importa: por ejemplo, las
fechas geológicas (9) deben ir después de quitar separadores de miles (8), y las expresiones de varias
palabras (10) deben ir antes de tokenizar (11), porque la tokenización separa `t. rex` en dos tokens.

| # | Paso | Regla | Lucene | Perfiles |
|---|---|---|---|---|
| 1 | **Unicode NFKC** | Normalización de compatibilidad (UAX #15): `ﬁ`→`fi`, `²`→`2`, espacio duro→espacio | `Preprocesador` (`java.text.Normalizer`) | todos (`nfkc`) |
| 2 | **Comillas y guiones** | `‘ ’ ‚ ‛ ′ ʼ \`` → `'`; `‐ ‑ ‒ – — ― −` → `-` | `Preprocesador` | siempre |
| 3 | **Minúsculas** | `str.lower()` / `toLowerCase(Locale.ROOT)` | `Preprocesador` | siempre |
| 4 | **Unir guiones de fin de línea** | `([a-z])-[ \t]*\r?\n[ \t]*([a-z])` → `\1\2` (`fos-\nsil`→`fossil`) | `Preprocesador` | todos (`unir_guiones`) |
| 5 | **Plegar diacríticos** | NFD + quitar marcas `\p{Mn}` + tabla `recursos/plegado.txt` (`ß`→`ss`, `æ`→`ae`…): `café`→`cafe` | `Preprocesador` | todos (`plegar_diacriticos`) |
| 6 | **Posesivos y contracciones** | quitar `'s` final; quitar `'` entre letras (`don't`→`dont`) | `Preprocesador` | siempre |
| 7 | **Fechas de calendario** | ISO `2026-11-19`, `19 November 2026`, `November 19th, 2026` → `20261119`; `Sept. 2021` → `202109`. Se valida mes 1–12 y día 1–31; si no es válida, se deja igual | `Preprocesador` | P3 (`fechas`) |
| 8 | **Números** | quitar la coma de miles: `1,500,000`→`1500000` (solo si va seguida de exactamente 3 dígitos) | `Preprocesador` | P2, P3 (`numeros = normalizar`) |
| 9 | **Tiempo geológico** | `66 million years ago`, `66-million-year-old`, `66 Ma`, `66 mya`, `66 myr` → `66ma`; igual con `billion`/`Ga`/`bya` → `ga` y `thousand`/`ka`/`kya` → `ka` | `Preprocesador` | P3 (`fechas_geologicas`) |
| 10 | **Expresiones de varias palabras** | `recursos/multipalabras.txt`: binomiales (`T. rex`→`tyrannosaurus_rex`), eventos (`K–Pg`, `K/T`, `Cretaceous–Paleogene` → `kpg`), términos compuestos (`mass extinction`, `non-avian`) y tesauro descriptivo (`bird-hipped`→`ornithischian`). Gana la frase más larga y se exige frontera de palabra | `Preprocesador` | P3 (`multipalabras`) |
| 11 | **Tokenización** | `[0-9]+(?:\.[0-9]+)+[a-z]*` \| `[a-z0-9]+(?:_[a-z0-9]+)*`. Todo lo demás separa | `PatternTokenizer` | siempre |
| 12 | **Longitud** | se descartan términos de menos de `longitud_minima` (2) o más de `longitud_maxima` (40) caracteres | `LengthFilter` | todos |
| 13 | **Palabras vacías** | lista del archivo `stopwords` | `StopFilter` | todos |
| 14 | **Tesauro** | `recursos/tesauro.txt`, un término → un término: ortografía británica → estadounidense (`palaeontology`→`paleontology`, `colour`→`color`), coloquial → canónico (`dino`→`dinosaur`) | `MapeoFilter` | P3 (`tesauro`) |
| 15 | **Términos protegidos** | si el término cumple **completo** la regex `protegidos`, no se le aplican raíces (géneros, términos con `_` o dígitos) | `PatternKeywordMarkerFilter` | P2, P3 |
| 16 | **Raíces** | `snowball`: Porter2 (Snowball English) · `lemas`: diccionario `forma→lema` de WordNet · `ninguna` | `SnowballFilter(EnglishStemmer)` · `StemmerOverrideFilter` | P2: snowball · P3: lemas |

### Reglas de implementación para que Python y Java coincidan

- **No usar `\s`, `\d`, `\w` ni `\b`.** En Python esas clases abarcan Unicode y en Java solo ASCII.
  Todas las clases se escriben explícitas: espacio = `[ \t\n\x0b\f\r]`, frontera = `(?<![a-z0-9_])`.
- Todas las expresiones se aplican **después** de pasar a minúsculas, sin banderas `(?i)`.
- Las alternativas (meses, frases) se ordenan igual en los dos lados: primero las más largas, y a
  igual longitud, en orden alfabético.
- Los reemplazos calculados (fechas, frases) se insertan como texto literal (`Matcher.quoteReplacement` en Java).
- `PatternKeywordMarkerFilter` usa `matches()`, que exige que la regex coincida con el término completo;
  en Python se usa `re.fullmatch`.
- Los *offsets* de Lucene se refieren al texto ya preprocesado (el índice no los usa).

## 3. Justificación de cada política

**Unicode NFKC (1) y plegado (5).** El 29 % del texto viene de PDF, cuya extracción produce
ligaduras tipográficas (`ﬁ`, `ﬂ`) y caracteres de compatibilidad. Sin NFKC, `ﬁssure` y `fissure` serían
dos términos distintos. El plegado de diacríticos unifica nombres de lugares y personas con y sin
tilde (`Ñandú`/`Nandu`). Este tipo de normalización por equivalencia es la recomendada en Manning et
al. (2008, §2.2.3), y las formas de normalización están definidas en el estándar Unicode (UAX #15).

**Unir guiones de fin de línea (4).** Los PDF parten palabras al final de la línea (`fos-\nsil`). Sin
este paso aparecen términos basura (`fos`, `sil`) que inflan el vocabulario y hacen que se pierda el
término real. Costo: un compuesto con guion legítimo que cae justo al final de línea (`bird-\nlike`)
se une como `birdlike`, lo cual es raro y aceptable.

**Minúsculas (3).** Es la normalización estándar de *case-folding* (Manning et al., 2008, §2.2.3). Los
nombres propios que sí importan (géneros, binomiales) se tratan con las políticas 10 y 15, no
conservando las mayúsculas.

**Posesivos y contracciones (6).** `dinosaur's` y `dinosaur` deben ser el mismo término. Lucene hace lo
mismo con `EnglishPossessiveFilter`; aquí se hace en la etapa de texto para que sea idéntico en ambos
lados. Las contracciones quedan como una palabra (`dont`) y la lista de Snowball las trata como vacías.

**Fechas (7).** Las consultas del colectivo son sobre todo informativas (Broder, 2002) y las fechas de
calendario aparecen en noticias de descubrimientos. Un único formato ISO 8601 compacto (`yyyymmdd`)
hace que `19 November 2026`, `November 19, 2026` y `2026-11-19` sean el mismo término. Las fechas
numéricas con barra (`11/19/2026`) **no** se convierten, porque las fuentes británicas usan día/mes y
las estadounidenses mes/día, así que el formato es ambiguo.

**Números (8).** `1,500,000` se tokenizaría como `1`, `500`, `000`: tres términos sin sentido. Al
quitar la coma de miles queda un término con el valor real.

**Tiempo geológico (9).** Es la "fecha" del dominio y aparece en consultas típicas del colectivo
(*when did Stegosaurus live*). La notación `Ma` (mega-annum) es la de la Comisión Internacional de
Estratigrafía (Cohen et al., 2013). Unificar `66 million years ago`, `66 Ma` y `66-million-year-old` en
`66ma` reduce el vocabulario y permite buscar por edad. Para evitar falsos positivos se exige la
palabra `years` después de `million` (`6 million people` no se convierte).

**Expresiones de varias palabras (10).** Los nombres binomiales (*Tyrannosaurus rex*) son la unidad de
significado del dominio; indexarlos como un solo término evita confundir `rex` suelto, y unifica las
abreviaturas (`T. rex`, `T-rex`). Las siglas con guion o barra (`K-Pg`, `K/T`) se partirían en
tokens de una letra que el filtro de longitud descarta, así que se perderían. El tesauro descriptivo
(`bird-hipped`→`ornithischian`) conecta el vocabulario escolar del colectivo (12–25 años) con el
técnico de las fuentes universitarias. Es la idea de tesauro y expansión de Manning et al. (2008, §9.2.2),
aplicada al indexar con un término canónico en lugar de expandir: así el índice no crece.

**Tokenización (11).** Se usa una expresión regular explícita en lugar del `StandardTokenizer` de
Lucene (reglas de segmentación UAX #29), porque UAX #29 es difícil de replicar exactamente fuera de
Lucene, y la equivalencia exacta con el índice manual es obligatoria. Se conservan los decimales
(`3.5`, `145.5ma`) y los términos unidos con `_`. Las letras no latinas que quedan después del
plegado (griego, CJK) funcionan como separadores: la colección es en inglés y esos caracteres son
símbolos (δ¹³C) o ruido.

**Longitud (12).** Las letras sueltas (`a`, `s` de restos de abreviaturas) no discriminan, y los
términos de más de 40 caracteres son casi siempre basura de la extracción (URLs pegadas, cadenas de
ADN, tablas). Ambos extremos inflan el vocabulario.

**Palabras vacías (13).** Las palabras más frecuentes de la colección son vacías (*the* 3 000 825,
*of* 1 949 724, *and* 1 491 045; ver documento del proyecto 1). Por la ley de Zipf ocupan una
fracción enorme de las listas de *postings* y casi no aportan al ranking TF-IDF (su IDF es ≈ 0).
Se usan dos listas para poder comparar: la corta de Lucene (33 palabras, P1) y la de Snowball
(≈150, P2/P3; Fox, 1989, analiza cómo se construyen estas listas). La lista de Snowball se adaptó: se
quitaron las contracciones que, sin apóstrofo, son palabras reales (`she'll`→`shell`, `we'll`→`well`,
`she'd`→`shed`), porque *shell* es un término importante del dominio.

**Tesauro (14).** Las fuentes británicas y estadounidenses escriben el mismo concepto de dos formas
(`palaeontology`/`paleontology`). Sin unificarlas, una consulta encuentra solo la mitad de los
documentos y el vocabulario se duplica. El stemmer no resuelve esto: `palaeontolog` ≠ `paleontolog`.

**Términos protegidos (15).** Los stemmers cortan los nombres de género: Porter2 reduce
`Triceratops`→`triceratop`, lo que lo confunde con otras formas. Se protegen por sufijo (`-saurus`,
`-raptor`, `-ceratops`, `-odon`, `-pteryx`…, como en la política P4 del arañador) y también los términos
con `_` o dígitos, que ya son canónicos.

**Raíces (16).** El *stemming* agrupa variantes morfológicas (`fossils`, `fossilized`, `fossilization`
→ `fossil`), lo que mejora la exhaustividad y reduce el vocabulario (Harman, 1991; Hull, 1996). Se
usa Porter2/Snowball (Porter, 1980; Porter, 2001) porque Lucene lo trae y existe la misma
implementación en Python. La **lematización** es más conservadora: produce palabras reales
(`studies`→`study`, `teeth`→`tooth`, `mice`→`mouse`) y no mezcla `fossilization` con `fossil`. Lucene
no trae un lematizador de inglés, así que se usa un **diccionario** generado de WordNet (Miller, 1995) y
aplicado con `StemmerOverrideFilter`. Como no se usa etiquetado gramatical, para una forma ambigua
se elige el lema más frecuente en SemCor (`found`→`find`, `left`→`leave`). Es una limitación
conocida, pero determinista e idéntica en los dos lados.

## 4. Perfiles (los 3 índices que pide la rúbrica)

| Perfil | Archivo | Qué agrega | Para qué |
|---|---|---|---|
| **P1 base** | `perfiles/p1_base.conf` | NFKC, guiones de PDF, diacríticos, minúsculas, tokenización, longitud, stopwords de Lucene (33) | Línea base: medir cuánto aportan los demás |
| **P2 stemming** | `perfiles/p2_stemming.conf` | P1 + números + stopwords de Snowball + géneros protegidos + Porter2 | Máxima reducción de vocabulario |
| **P3 completo** | `perfiles/p3_completo.conf` | P2 sin stemmer + fechas + tiempo geológico + multipalabras + tesauro + lemas | Máxima calidad semántica para el dominio |

Resultado en la muestra (10 documentos del proyecto 1, 11 314 palabras, 3 523 formas distintas al
separar solo por espacios). Son datos preliminares; las estadísticas finales se sacan sobre la colección completa:

| Perfil | Términos | Vocabulario | Velocidad Python |
|---|---:|---:|---:|
| P1 base | 8 049 | 2 421 | ≈ 88 mil palabras/s |
| P2 stemming | 6 862 | 1 930 | ≈ 81 mil palabras/s |
| P3 completo | 6 649 | 1 957 | ≈ 66 mil palabras/s |

## 5. Formato del archivo de configuración

Formato INI de Linux (el de `configparser` de Python y de muchos `/etc/*.conf`): secciones `[nombre]`,
líneas `clave = valor`, comentarios con `#` o `;`. Las rutas son relativas a la carpeta del `.conf`.
Los booleanos son `si`/`no`. Los indexadores pueden agregar sus propias secciones (por ejemplo
`[indexador]`, `[coleccion]`); los lectores de normalización las ignoran.

```ini
[perfil]
nombre = p2_stemming

[normalizacion]
# pasos 1, 4 y 5
nfkc = si
unir_guiones = si
plegar_diacriticos = si
plegado = ../recursos/plegado.txt
# paso 7
fechas = no
# paso 8: conservar | normalizar
numeros = normalizar
# paso 9
fechas_geologicas = no
# paso 10: archivo o vacio
multipalabras =
stopwords = ../recursos/stopwords_snowball.txt
# paso 14: archivo o vacio
tesauro =
protegidos = .*[_0-9].*|.*(saurus|raptor|ceratops|odon|pteryx|mimus|titan|suchus|venator|lophus|cephale|pelta|gnathus|nychus|rhynchus)
# paso 16: ninguna | snowball | lemas
raices = snowball
# archivo forma<TAB>lema, obligatorio si raices = lemas
lemas =
longitud_minima = 2
longitud_maxima = 40
```

Los comentarios van en su propia línea: no se permiten comentarios al final de una línea con valor
(quedarían como parte del valor) ni valores que ocupen varias líneas.

## 6. Recursos

| Archivo | Formato | Origen |
|---|---|---|
| `recursos/stopwords_lucene.txt` | una palabra por línea | `EnglishAnalyzer.ENGLISH_STOP_WORDS_SET` de Lucene |
| `recursos/stopwords_snowball.txt` | una palabra por línea | lista de Snowball, adaptada (sección 3) |
| `recursos/plegado.txt` | `c => reemplazo` | propio |
| `recursos/tesauro.txt` | `forma1, forma2 => canonica` | propio (ortografía GB/US y dominio) |
| `recursos/multipalabras.txt` | `frase1 \| frase2 => termino` | propio (binomiales de géneros de la lista temática del proyecto 1) |
| `recursos/lemas_en.txt` | `forma<TAB>lema` | generado con `herramientas/generar_lemas.py` desde WordNet 3.0 |

En todos, las líneas que empiezan con `#` y las vacías se ignoran.

## 7. Versiones fijadas (importante)

Al comparar las dos implementaciones salió algo que no es obvio: **el "mismo" stemmer Snowball no da
los mismos resultados en todas las versiones**. El paquete `snowballstemmer` 3.x de Python usa
Snowball 3.0, que agrega reglas nuevas (`palaeontologists`→`palaeontolog`, `added`→`add`). Lucene 10.x
trae una versión intermedia (`add` pero `palaeontologist`), que no coincide con ningún paquete publicado
de Python. La pareja que coincide exactamente es:

| Lado | Versión |
|---|---|
| Apache Lucene | **9.12.1** (`java/build.gradle`) |
| Python `snowballstemmer` | **2.2.0** (`python/requirements.txt`) |

Las pruebas `test_version_snowball` (Python) y `versionSnowball` (Java) fallan si alguien cambia una
de las dos versiones.

## 8. Cómo se demuestra la equivalencia

1. `pruebas/golden.tsv`: 20 casos (uno por regla, con casos límite) × 3 perfiles, cada uno con su
   salida esperada. Los corren `python/tests/test_golden.py` y `java/.../GoldenTest.java`.
2. `herramientas/verificar_equivalencia.py`: corre las dos implementaciones sobre documentos reales
   y compara término por término. Resultado actual sobre la muestra más los casos golden:
   **idénticos en los 3 perfiles** (8 245 / 7 053 / 6 806 términos).

## 9. Uso

```bash
# Python (indexador manual)
pip install -r normalizacion/python/requirements.txt
```
```python
import sys; sys.path.insert(0, "normalizacion/python")
from paleonorm import Normalizador
norm = Normalizador.desde_archivo("normalizacion/perfiles/p2_stemming.conf")
terminos = norm.terminos(texto)          # lista de str, en orden de aparicion
```

```java
// Lucene: dependencia del proyecto normalizacion/java (paleobusca:paleonorm)
Analyzer analyzer = PaleoAnalyzer.desdeArchivo(Path.of("normalizacion/perfiles/p2_stemming.conf"));
IndexWriterConfig iwc = new IndexWriterConfig(analyzer);
```

```bash
# Pruebas y verificación
cd normalizacion/python && python -m pytest
cd normalizacion/java && ./gradlew test installDist
python normalizacion/herramientas/extraer_muestra.py RUTA_PROYECTO_1     # muestra de prueba
python normalizacion/herramientas/verificar_equivalencia.py [CARPETA_COLECCION] [--max-docs N]

# Línea de comandos (misma interfaz en ambos lados)
PYTHONPATH=normalizacion/python python -m paleonorm --conf normalizacion/perfiles/p3_completo.conf < doc.txt
normalizacion/java/build/install/paleonorm/bin/paleonorm --conf normalizacion/perfiles/p3_completo.conf < doc.txt
```

Para cambiar una regla: editar el recurso o el código **en ambos lados**, agregar el caso en
`pruebas/casos.txt`, correr `herramientas/generar_golden.py`, **revisar el diff de `golden.tsv` a mano**
y correr las dos suites de pruebas.

## 10. Limitaciones conocidas

- Lematización sin etiquetado gramatical: `left`→`leave`, `saw`→`see`, `remains`→`remain`.
- La validación de fechas es simple (`2020-02-30` se acepta como `20200230`).
- Los rangos geológicos (`145 to 66 million years ago`) solo convierten el segundo número.
- Las fechas numéricas con barra no se normalizan (son ambiguas).
- Los binomiales se reconocen solo si están en `multipalabras.txt` (no hay detección automática,
  porque la regla "palabra con mayúscula + palabra en minúscula" da demasiados falsos positivos).
- Un guion de fin de línea legítimo se une (`bird-\nlike`→`birdlike`).

## Bibliografía

- Broder, A. (2002). A taxonomy of web search. *ACM SIGIR Forum*, 36(2), 3–10.
- Cohen, K. M., Finney, S. C., Gibbard, P. L. y Fan, J.-X. (2013). The ICS International Chronostratigraphic Chart. *Episodes*, 36(3), 199–204.
- Davis, M. y Whistler, K. *Unicode Standard Annex #15: Unicode Normalization Forms*. Unicode Consortium.
- Fox, C. (1989). A stop list for general text. *ACM SIGIR Forum*, 24(1–2), 19–21.
- Harman, D. (1991). How effective is suffixing? *Journal of the American Society for Information Science*, 42(1), 7–15.
- Hull, D. A. (1996). Stemming algorithms: A case study for detailed evaluation. *Journal of the American Society for Information Science*, 47(1), 70–84.
- ISO 8601-1:2019. *Date and time — Representations for information interchange*.
- Manning, C. D., Raghavan, P. y Schütze, H. (2008). *Introduction to Information Retrieval*, cap. 2 (The term vocabulary and postings lists) y cap. 9. Cambridge University Press.
- Miller, G. A. (1995). WordNet: A lexical database for English. *Communications of the ACM*, 38(11), 39–41.
- Porter, M. F. (1980). An algorithm for suffix stripping. *Program*, 14(3), 130–137.
- Porter, M. F. (2001). *Snowball: A language for stemming algorithms*. https://snowballstem.org/
- The Apache Software Foundation. *Apache Lucene 9.12 — analysis-common API*. https://lucene.apache.org/
