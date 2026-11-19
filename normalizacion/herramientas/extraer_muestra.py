"""Crea una muestra de textos .txt a partir de los HTML de prueba del proyecto 1.

Usa el mismo extractor del arañador (procesamiento.extraer_html), asi la muestra se parece a los
.txt reales de la coleccion. Sirve para probar el normalizador y comparar Python contra Lucene
mientras no se tenga la coleccion completa en la maquina.

    python herramientas/extraer_muestra.py RUTA_PROYECTO_1 [--salida pruebas/muestra]
"""

import argparse
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proyecto1", help="carpeta del repositorio del proyecto 1")
    ap.add_argument("--salida", default=str(AQUI.parent / "pruebas" / "muestra"))
    args = ap.parse_args()

    arana = Path(args.proyecto1) / "Arañador Py"
    sys.path.insert(0, str(arana))
    from arana.procesamiento import extraer_html

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    for html in sorted((arana / "tests" / "fixtures").glob("*.htm*")):
        pagina = extraer_html(html.read_bytes(), "text/html", "https://" + html.stem.split("_")[0] + "/")
        destino = salida / (html.name.split(".html")[0] + ".txt")
        destino.write_text(pagina.texto, encoding="utf-8", newline="\n")
        print(f"{destino.name}: {len(pagina.texto.split())} palabras")


if __name__ == "__main__":
    main()
