"""Lectura del archivo de configuracion (.conf estilo INI de Linux) y de los recursos que referencia.

El mismo formato lo lee la implementacion en Java (ConfigNormalizacion.java); cualquier cambio aqui
debe replicarse alla y documentarse en ESPECIFICACION.md.
"""

import configparser
from dataclasses import dataclass, field
from pathlib import Path

SECCION = "normalizacion"
RAICES_VALIDAS = ("ninguna", "snowball", "lemas")
NUMEROS_VALIDOS = ("conservar", "normalizar")


def _lineas_utiles(ruta):
    """Lineas sin espacios a los lados, sin vacias ni comentarios (#)."""
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith("#"):
                yield linea


def cargar_lista(ruta):
    return frozenset(_lineas_utiles(ruta))


def cargar_mapeo(ruta, separador_izq=","):
    """Lineas 'forma1<sep>forma2 => salida'. Devuelve {forma: salida}. La ultima definicion gana."""
    mapeo = {}
    for linea in _lineas_utiles(ruta):
        izq, _, der = linea.partition("=>")
        salida = der.strip()
        if not salida:
            raise ValueError(f"{ruta}: linea sin '=> salida': {linea!r}")
        for forma in izq.split(separador_izq):
            forma = forma.strip()
            if forma:
                mapeo[forma] = salida
    return mapeo


def cargar_lemas(ruta):
    """Archivo TSV 'forma<TAB>lema'."""
    lemas = {}
    for linea in _lineas_utiles(ruta):
        forma, _, lema = linea.partition("\t")
        if lema:
            lemas[forma.strip()] = lema.strip()
    return lemas


@dataclass
class ConfigNormalizacion:
    nombre: str = "sin_nombre"
    nfkc: bool = True
    unir_guiones: bool = True
    plegar_diacriticos: bool = True
    plegado: dict = field(default_factory=dict)
    fechas: bool = False
    numeros: str = "conservar"
    fechas_geologicas: bool = False
    multipalabras: dict = field(default_factory=dict)
    stopwords: frozenset = frozenset()
    tesauro: dict = field(default_factory=dict)
    protegidos: str = ""
    raices: str = "ninguna"
    lemas: dict = field(default_factory=dict)
    longitud_minima: int = 1
    longitud_maxima: int = 255

    @classmethod
    def desde_archivo(cls, ruta_conf, con_lemas=True):
        """con_lemas=False ignora el diccionario de lemas (lo usa generar_lemas.py para crearlo)."""
        ruta_conf = Path(ruta_conf)
        cp = configparser.ConfigParser(interpolation=None, comment_prefixes=("#", ";"),
                                       inline_comment_prefixes=None)
        with open(ruta_conf, encoding="utf-8") as f:
            cp.read_file(f)
        if not cp.has_section(SECCION):
            raise ValueError(f"{ruta_conf}: falta la seccion [{SECCION}]")
        s = cp[SECCION]
        base = ruta_conf.parent

        def booleano(clave, defecto):
            valor = s.get(clave, "").strip().lower()
            if not valor:
                return defecto
            if valor not in ("si", "no"):
                raise ValueError(f"{ruta_conf}: {clave} debe ser 'si' o 'no', no {valor!r}")
            return valor == "si"

        def ruta(clave):
            valor = s.get(clave, "").strip()
            return (base / valor) if valor else None

        def con_ruta(clave, cargador, vacio):
            r = ruta(clave)
            return cargador(r) if r else vacio

        cfg = cls(
            nombre=cp.get("perfil", "nombre", fallback=ruta_conf.stem).strip(),
            nfkc=booleano("nfkc", True),
            unir_guiones=booleano("unir_guiones", True),
            plegar_diacriticos=booleano("plegar_diacriticos", True),
            plegado=con_ruta("plegado", cargar_mapeo, {}),
            fechas=booleano("fechas", False),
            numeros=s.get("numeros", "conservar").strip().lower() or "conservar",
            fechas_geologicas=booleano("fechas_geologicas", False),
            multipalabras=con_ruta("multipalabras", lambda r: cargar_mapeo(r, "|"), {}),
            stopwords=con_ruta("stopwords", cargar_lista, frozenset()),
            tesauro=con_ruta("tesauro", cargar_mapeo, {}),
            protegidos=s.get("protegidos", "").strip(),
            raices=s.get("raices", "ninguna").strip().lower() or "ninguna",
            lemas=con_ruta("lemas", cargar_lemas, {}) if con_lemas else {},
            longitud_minima=s.getint("longitud_minima", 1),
            longitud_maxima=s.getint("longitud_maxima", 255),
        )
        if cfg.raices not in RAICES_VALIDAS:
            raise ValueError(f"{ruta_conf}: raices debe ser uno de {RAICES_VALIDAS}")
        if cfg.numeros not in NUMEROS_VALIDOS:
            raise ValueError(f"{ruta_conf}: numeros debe ser uno de {NUMEROS_VALIDOS}")
        if con_lemas and cfg.raices == "lemas" and not cfg.lemas:
            raise ValueError(f"{ruta_conf}: raices = lemas requiere un archivo de lemas no vacio")
        return cfg
