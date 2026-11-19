"""PaleoBusca - normalizacion de texto para el indice (proyecto 2).

Uso desde el indexador:
    from paleonorm import Normalizador
    norm = Normalizador.desde_archivo("normalizacion/perfiles/p2_stemming.conf")
    terminos = norm.terminos(texto_del_documento)
"""

from .config import ConfigNormalizacion
from .normalizador import Normalizador

__all__ = ["ConfigNormalizacion", "Normalizador"]
