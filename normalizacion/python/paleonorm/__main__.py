"""Linea de comandos: normaliza texto y escribe los terminos.

    python -m paleonorm --conf perfiles/p2_stemming.conf < documento.txt
    python -m paleonorm --conf perfiles/p2_stemming.conf --lineas < entradas.txt

Con --lineas cada linea de entrada es un documento aparte (la secuencia "\\n" dentro de la linea
representa un salto de linea real) y se imprime una linea de terminos por cada una. Es el mismo
formato que usa la herramienta Tokenizar de Java, para poder comparar ambas salidas.
"""

import argparse
import sys

from .normalizador import Normalizador


def main(argv=None):
    ap = argparse.ArgumentParser(prog="paleonorm", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conf", required=True, help="archivo .conf del perfil de normalizacion")
    ap.add_argument("--lineas", action="store_true", help="un documento por linea")
    args = ap.parse_args(argv)

    norm = Normalizador.desde_archivo(args.conf)
    entrada = open(sys.stdin.fileno(), encoding="utf-8", newline="")
    salida = open(sys.stdout.fileno(), "w", encoding="utf-8", newline="\n", closefd=False)
    if args.lineas:
        for linea in entrada:
            linea = linea.rstrip("\r\n").replace("\\n", "\n")
            salida.write(" ".join(norm.terminos(linea)) + "\n")
    else:
        salida.write("\n".join(norm.terminos(entrada.read())) + "\n")
    salida.flush()


if __name__ == "__main__":
    main()
