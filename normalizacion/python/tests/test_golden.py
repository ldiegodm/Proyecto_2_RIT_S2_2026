"""Pruebas de la normalizacion en Python contra pruebas/golden.tsv (las mismas que corre Java).

    cd normalizacion/python && python -m pytest
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "python"))

from paleonorm import Normalizador   # noqa: E402
from paleonorm.normalizador import escapar_literal, patron_frase   # noqa: E402


def casos():
    for n, linea in enumerate((RAIZ / "pruebas" / "golden.tsv").read_text(encoding="utf-8").splitlines(), 1):
        if linea and not linea.startswith("#") and not linea.startswith("perfil\t"):
            perfil, entrada, esperado = linea.split("\t")
            yield pytest.param(perfil, entrada.replace("\\n", "\n"), esperado, id=f"{n}-{perfil}")


_cache = {}


def normalizador(perfil):
    if perfil not in _cache:
        _cache[perfil] = Normalizador.desde_archivo(RAIZ / "perfiles" / f"{perfil}.conf")
    return _cache[perfil]


@pytest.mark.parametrize("perfil,entrada,esperado", list(casos()))
def test_golden(perfil, entrada, esperado):
    assert " ".join(normalizador(perfil).terminos(entrada)) == esperado


def test_version_snowball():
    # Lucene 9.12 trae el algoritmo Snowball 2.x; snowballstemmer 3.x cambia stems (p. ej. -ogist -> -og).
    import snowballstemmer
    assert snowballstemmer.stemmer("english").stemWord("palaeontologists") == "palaeontologist"
    assert snowballstemmer.stemmer("english").stemWord("added") == "ad"


def test_escapar_literal():
    assert escapar_literal("k-pg") == "k\\-pg"
    assert patron_frase("t.  rex") == "t\\.[ \\t\\n\\x0b\\f\\r]+rex"


def test_documento_vacio():
    assert normalizador("p3_completo").terminos("") == []
