"""Genera recursos/lemas_en.txt (forma<TAB>lema) a partir de WordNet.

La lematizacion del perfil P3 es por diccionario: Lucene no trae un lematizador de ingles, pero si
puede aplicar un diccionario con StemmerOverrideFilter. Este script construye ese diccionario una sola
vez para que Python y Java usen exactamente el mismo archivo.

Fuentes de formas:
  1. Flexiones regulares de todos los lemas de una palabra de WordNet (plurales, -ed, -ing, -er, -est,
     con las reglas de ortografia del ingles); solo se conservan las que morphy reconoce.
  2. Las listas de excepciones de WordNet (formas irregulares: mice -> mouse, found -> find).
  3. Opcional: el vocabulario de la coleccion, normalizado con el perfil indicado pero sin raices.
Como el lema de una forma depende solo de WordNet, agregar formas nunca cambia las entradas que ya
existian: el diccionario es estable aunque se regenere con otra coleccion.

Para cada forma se piden a WordNet (morphy) los lemas candidatos de sustantivo, verbo, adjetivo y
adverbio y se elige el de mayor frecuencia en SemCor (Lemma.count()); en empate gana el orden
sustantivo > verbo > adjetivo > adverbio y luego el mas corto. Ej.: bones -> {bones, bone} -> bone;
species -> {species, specie} -> species.

Uso:
    python -m pip install nltk
    python herramientas/generar_lemas.py --conf perfiles/p3_completo.conf [RUTA_COLECCION ...]
RUTA puede ser una carpeta (se leen todos los .txt recursivamente) o archivos .txt sueltos.
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "python"))

from paleonorm.config import ConfigNormalizacion   # noqa: E402
from paleonorm.normalizador import Normalizador   # noqa: E402

SOLO_LETRAS = re.compile(r"[a-z]+")
POS = ("n", "v", "a", "r")
VOCALES = set("aeiou")


def flexiones(lema, pos):
    """Formas regulares candidatas de un lema (se filtran despues con morphy)."""
    f = set()
    doble = (len(lema) >= 3 and lema[-1] not in VOCALES | {"w", "x", "y"}
             and lema[-2] in VOCALES and lema[-3] not in VOCALES)
    if pos in ("n", "v"):
        f |= {lema + "s", lema + "es"}
        if lema.endswith("y") and lema[-2:-1] not in VOCALES:
            f.add(lema[:-1] + "ies")
    if pos == "v":
        base = lema[:-1] if lema.endswith("e") else lema
        f |= {base + "ed", base + "ing", lema + "d"}
        if lema.endswith("y") and lema[-2:-1] not in VOCALES:
            f.add(lema[:-1] + "ied")
        if lema.endswith("ie"):
            f.add(lema[:-2] + "ying")
        if doble:
            f |= {lema + lema[-1] + "ed", lema + lema[-1] + "ing"}
    if pos == "a":
        base = lema[:-1] if lema.endswith("e") else lema
        f |= {base + "er", base + "est"}
        if lema.endswith("y") and lema[-2:-1] not in VOCALES:
            f |= {lema[:-1] + "ier", lema[:-1] + "iest"}
        if doble:
            f |= {lema + lema[-1] + "er", lema + lema[-1] + "est"}
    return f


def archivos(rutas):
    for r in map(Path, rutas):
        if r.is_dir():
            yield from sorted(r.rglob("*.txt"))
        else:
            yield r


def vocabulario(norm, rutas):
    vocab = Counter()
    for i, ruta in enumerate(archivos(rutas), 1):
        vocab.update(norm.terminos(ruta.read_text(encoding="utf-8", errors="replace")))
        if i % 2000 == 0:
            print(f"  {i} documentos, {len(vocab)} formas", file=sys.stderr)
    return vocab


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conf", required=True, help="perfil cuyo preprocesamiento se usa (p. ej. p3_completo.conf)")
    ap.add_argument("--salida", default=str(AQUI.parent / "recursos" / "lemas_en.txt"))
    ap.add_argument("--min-frecuencia", type=int, default=1, help="ignorar formas menos frecuentes")
    ap.add_argument("rutas", nargs="*", help="carpetas o archivos .txt de la coleccion")
    args = ap.parse_args()

    import nltk
    nltk.download("wordnet", quiet=True)
    from nltk.corpus import wordnet as wn

    cfg = ConfigNormalizacion.desde_archivo(args.conf, con_lemas=False)
    cfg.raices = "ninguna"
    cfg.lemas = {}
    norm = Normalizador(cfg)

    formas = set()
    if args.rutas:
        vocab = vocabulario(norm, args.rutas)
        formas |= {f for f, n in vocab.items() if n >= args.min_frecuencia}
        print(f"vocabulario de la coleccion: {len(vocab)} formas", file=sys.stderr)
    for pos in POS:
        formas |= set(wn._exception_map[pos])        # formas irregulares de WordNet
        for lema in wn.all_lemma_names(pos):           # flexiones regulares
            if SOLO_LETRAS.fullmatch(lema):
                formas |= flexiones(lema, pos)
    formas = {f for f in formas if SOLO_LETRAS.fullmatch(f) and f not in cfg.stopwords}

    cache = {}

    def frecuencia(lema):
        if lema not in cache:
            cache[lema] = sum(l.count() for l in wn.lemmas(lema))
        return cache[lema]

    lemas = {}
    for forma in sorted(formas):
        candidatos = []
        for orden, pos in enumerate(POS):
            for c in wn._morphy(forma, pos):
                if SOLO_LETRAS.fullmatch(c):
                    candidatos.append((-frecuencia(c), orden, len(c), c))
        if candidatos:
            lema = min(candidatos)[3]
            if lema != forma:
                lemas[forma] = lema

    with open(args.salida, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Diccionario forma -> lema para el perfil P3. Generado con herramientas/generar_lemas.py\n")
        f.write("# a partir de WordNet 3.0 (Princeton). No editar a mano.\n")
        for forma in sorted(lemas):
            f.write(f"{forma}\t{lemas[forma]}\n")
    print(f"{len(lemas)} entradas -> {args.salida}", file=sys.stderr)


if __name__ == "__main__":
    main()
