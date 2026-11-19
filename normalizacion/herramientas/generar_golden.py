"""Regenera pruebas/golden.tsv a partir de pruebas/casos.txt usando la implementacion de Python.

El archivo resultante es la referencia que deben cumplir Python y Lucene. OJO: se genera con el
codigo actual, asi que despues de regenerarlo hay que revisar a mano (git diff) que cada cambio sea
el esperado antes de commitearlo.

    python herramientas/generar_golden.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "python"))

from paleonorm import Normalizador   # noqa: E402


def main():
    perfiles = sorted(p.stem for p in (RAIZ / "perfiles").glob("*.conf"))
    norms = {p: Normalizador.desde_archivo(RAIZ / "perfiles" / f"{p}.conf") for p in perfiles}
    out = ["# Casos de prueba de la normalizacion (golden). Ambas implementaciones deben producir exactamente",
           "# la columna 'esperado' (terminos separados por un espacio). En 'entrada', \\n es un salto de linea.",
           "# Generado con herramientas/generar_golden.py desde pruebas/casos.txt y revisado a mano.",
           "perfil\tentrada\tesperado"]
    for linea in (RAIZ / "pruebas" / "casos.txt").read_text(encoding="utf-8").splitlines():
        if not linea.strip() or linea.startswith("#"):
            continue
        texto = linea.replace("\\n", "\n")
        for p in perfiles:
            out.append(f"{p}\t{linea}\t{' '.join(norms[p].terminos(texto))}")
    destino = RAIZ / "pruebas" / "golden.tsv"
    destino.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(out) - 4} casos -> {destino}")


if __name__ == "__main__":
    main()
