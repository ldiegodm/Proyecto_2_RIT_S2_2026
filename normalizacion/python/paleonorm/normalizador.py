"""Normalizador de PaleoBusca: texto -> lista de terminos del indice.

Implementa, paso por paso y en el mismo orden, la especificacion de normalizacion/ESPECIFICACION.md.
La version en Java (PaleoAnalyzer) debe producir exactamente los mismos terminos; eso se comprueba
con pruebas/golden.tsv y con herramientas/verificar_equivalencia.py.

Reglas para que Python y Java coincidan:
  * no usar \\s, \\d, \\w ni \\b (en Python abarcan Unicode y en Java solo ASCII): las clases van explicitas;
  * todas las expresiones se escriben despues de pasar a minusculas, sin banderas (?i);
  * las listas y mapeos salen de los mismos archivos de recursos.
"""

import re
import sys
import unicodedata

from .config import ConfigNormalizacion

# Espacio en blanco ASCII (igual que \s de Java).
WS = r"[ \t\n\x0b\f\r]"
# Caracteres que forman palabra para las fronteras (sustituye a \b).
NO_PAL_ANTES = r"(?<![a-z0-9_])"
NO_PAL_DESPUES = r"(?![a-z0-9_])"

# Paso 2: comillas simples tipograficas -> ' ; guiones tipograficos y signo menos -> -
RE_COMILLAS = re.compile("[‘’‚‛′ʼ`]")
RE_GUIONES = re.compile("[‐‑‒–—―−]")

# Paso 4: palabra cortada al final de linea (tipico de PDF): "fos-\nsil" -> "fossil"
RE_GUION_FIN_LINEA = re.compile(r"([a-z])-[ \t]*\r?\n[ \t]*([a-z])")

# Paso 5: marcas diacriticas (categoria Unicode Mn), igual que \p{Mn} en Java.
_MN = "".join(chr(c) for c in range(sys.maxunicode + 1)
              if unicodedata.category(chr(c)) == "Mn" and not 0xD800 <= c <= 0xDFFF)
RE_MARCAS = re.compile("[" + re.escape(_MN) + "]")

# Paso 6: posesivo y apostrofos internos
RE_POSESIVO = re.compile(r"'s" + NO_PAL_DESPUES)
RE_APOSTROFO_INTERNO = re.compile(r"(?<=[a-z0-9])'(?=[a-z0-9])")

# Paso 7: fechas de calendario
MESES = ["january", "february", "march", "april", "may", "june", "july", "august",
         "september", "october", "november", "december"]
ABREVIATURAS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
                "sept": 9, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
NUM_MES = {m: i + 1 for i, m in enumerate(MESES)} | ABREVIATURAS
_ALT_MESES = "|".join(sorted(NUM_MES, key=lambda m: (-len(m), m)))
_MES = NO_PAL_ANTES + "(" + _ALT_MESES + r")\.?"
_DIA = r"([0-9]{1,2})(?:st|nd|rd|th)?"
_ANIO = r"([0-9]{4})(?![0-9])"
RE_FECHA_ISO = re.compile(r"(?<![0-9])([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})(?![0-9])")
RE_FECHA_DMA = re.compile(r"(?<![a-z0-9_.])" + _DIA + WS + "+" + _MES + ",?" + WS + "+" + _ANIO)
RE_FECHA_MDA = re.compile(_MES + WS + "+" + _DIA + "," + "?" + WS + "+" + _ANIO)
RE_FECHA_MA = re.compile(_MES + ",?" + WS + "+" + _ANIO)

# Paso 8: separador de miles
RE_MILES = re.compile(r"(?<=[0-9]),(?=[0-9]{3}(?![0-9]))")

# Paso 9: tiempo geologico
_NUM = r"(?<![a-z0-9_.])([0-9]+(?:\.[0-9]+)?)" + "[ \t\n\x0b\f\r-]*"
_SEP = "[ \t\n\x0b\f\r-]+"
_ANIOS = r"years?(?:" + _SEP + r"(?:ago|old))?"
RE_GEO_GA = re.compile(_NUM + r"(?:billion" + _SEP + _ANIOS + r"|bya|gya|ga)" + NO_PAL_DESPUES)
RE_GEO_MA = re.compile(_NUM + r"(?:million" + _SEP + _ANIOS + r"|myr|mya|ma)" + NO_PAL_DESPUES)
RE_GEO_KA = re.compile(_NUM + r"(?:thousand" + _SEP + _ANIOS + r"|kyr|kya|ka)" + NO_PAL_DESPUES)

# Paso 11: tokenizacion
RE_TOKEN = re.compile(r"[0-9]+(?:\.[0-9]+)+[a-z]*|[a-z0-9]+(?:_[a-z0-9]+)*")

RE_WS = re.compile(WS + "+")


def escapar_literal(texto):
    """Escapa todo lo que no sea [a-z0-9] con '\\'. Valido igual en Python y en Java."""
    return "".join(c if ("a" <= c <= "z" or "0" <= c <= "9") else "\\" + c for c in texto)


def patron_frase(frase):
    """'t. rex' -> 't\\.' + WS+ + 'rex'"""
    return (WS + "+").join(escapar_literal(p) for p in RE_WS.split(frase.strip()) if p)


def _fecha(anio, mes, dia=None):
    if not 1 <= mes <= 12:
        return None
    if dia is None:
        return f"{anio}{mes:02d}"
    if not 1 <= dia <= 31:
        return None
    return f"{anio}{mes:02d}{dia:02d}"


class Normalizador:
    def __init__(self, config: ConfigNormalizacion):
        self.config = config
        self._plegado = str.maketrans(config.plegado) if config.plegado else None
        if config.multipalabras:
            frases = sorted(config.multipalabras, key=lambda f: (-len(f), f))
            self._re_multi = re.compile(NO_PAL_ANTES + "(?:" + "|".join(patron_frase(f) for f in frases)
                                        + ")" + NO_PAL_DESPUES)
            self._multi = {" ".join(RE_WS.split(f.strip())): v for f, v in config.multipalabras.items()}
        else:
            self._re_multi = None
        self._re_protegidos = re.compile(config.protegidos) if config.protegidos else None
        self._raices_cache = {}
        if config.raices == "snowball":
            import snowballstemmer
            self._stemmer = snowballstemmer.stemmer("english")

    @classmethod
    def desde_archivo(cls, ruta_conf):
        return cls(ConfigNormalizacion.desde_archivo(ruta_conf))

    # ---------------------------------------------------------------- etapa de texto (pasos 1-10)
    def preprocesar(self, texto: str) -> str:
        c = self.config
        if c.nfkc:                                                        # 1
            texto = unicodedata.normalize("NFKC", texto)
        texto = RE_COMILLAS.sub("'", texto)                               # 2
        texto = RE_GUIONES.sub("-", texto)
        texto = texto.lower()                                             # 3
        if c.unir_guiones:                                                # 4
            texto = RE_GUION_FIN_LINEA.sub(r"\1\2", texto)
        if c.plegar_diacriticos and not texto.isascii():                  # 5
            texto = RE_MARCAS.sub("", unicodedata.normalize("NFD", texto))
            if self._plegado:
                texto = texto.translate(self._plegado)
        texto = RE_POSESIVO.sub("", texto)                                # 6
        texto = RE_APOSTROFO_INTERNO.sub("", texto)
        if c.fechas:                                                      # 7
            texto = self._fechas(texto)
        if c.numeros == "normalizar":                                     # 8
            texto = RE_MILES.sub("", texto)
        if c.fechas_geologicas:                                           # 9
            texto = RE_GEO_GA.sub(r"\1ga", texto)
            texto = RE_GEO_MA.sub(r"\1ma", texto)
            texto = RE_GEO_KA.sub(r"\1ka", texto)
        if self._re_multi is not None:                                    # 10
            texto = self._re_multi.sub(lambda m: self._multi[" ".join(RE_WS.split(m.group(0)))], texto)
        return texto

    @staticmethod
    def _fechas(texto):
        def iso(m):
            return _fecha(int(m.group(1)), int(m.group(2)), int(m.group(3))) or m.group(0)

        def dma(m):
            return _fecha(int(m.group(3)), NUM_MES[m.group(2)], int(m.group(1))) or m.group(0)

        def mda(m):
            return _fecha(int(m.group(3)), NUM_MES[m.group(1)], int(m.group(2))) or m.group(0)

        def ma(m):
            return _fecha(int(m.group(2)), NUM_MES[m.group(1)]) or m.group(0)

        texto = RE_FECHA_ISO.sub(iso, texto)
        texto = RE_FECHA_DMA.sub(dma, texto)
        texto = RE_FECHA_MDA.sub(mda, texto)
        return RE_FECHA_MA.sub(ma, texto)

    # ---------------------------------------------------------------- etapa de terminos (pasos 11-16)
    def terminos(self, texto: str) -> list:
        c = self.config
        minimo, maximo = c.longitud_minima, c.longitud_maxima
        stop, tesauro = c.stopwords, c.tesauro
        raiz = self._raiz
        salida = []
        for tok in RE_TOKEN.findall(self.preprocesar(texto)):           # 11
            if not minimo <= len(tok) <= maximo:                          # 12
                continue
            if tok in stop:                                               # 13
                continue
            tok = tesauro.get(tok, tok)                                   # 14
            salida.append(raiz(tok))                                      # 15-16
        return salida

    def _raiz(self, tok):
        c = self.config
        if c.raices == "ninguna":
            return tok
        r = self._raices_cache.get(tok)
        if r is None:
            if self._re_protegidos is not None and self._re_protegidos.fullmatch(tok):   # 15
                r = tok
            elif c.raices == "snowball":                                                 # 16
                r = self._stemmer.stemWord(tok)
            else:
                r = c.lemas.get(tok, tok)
            self._raices_cache[tok] = r
        return r
