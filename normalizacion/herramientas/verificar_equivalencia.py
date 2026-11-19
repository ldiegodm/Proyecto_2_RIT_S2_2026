"""Comprueba que Python (paleonorm) y Lucene (PaleoAnalyzer) producen exactamente los mismos terminos.

Ejecuta ambas implementaciones sobre los mismos documentos con cada perfil y compara documento por
documento. Es la evidencia de que el indice manual y el de Lucene aplican la misma normalizacion.

    cd normalizacion/java && ./gradlew installDist        (una vez, compila la version Java)
    python herramientas/verificar_equivalencia.py [CARPETA_TXT ...] [--perfil p2_stemming] [--max-docs N]

Sin carpetas usa pruebas/muestra (ver extraer_muestra.py) mas las entradas de pruebas/golden.tsv.
Sale con codigo 1 si encuentra diferencias.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
JAVA_BIN = RAIZ / "java" / "build" / "install" / "paleonorm" / "bin" / ("paleonorm.bat" if os.name == "nt" else "paleonorm")


def documentos(carpetas, max_docs):
    docs = []
    for c in carpetas:
        for ruta in sorted(Path(c).rglob("*.txt")):
            docs.append((str(ruta), ruta.read_text(encoding="utf-8", errors="replace")))
            if max_docs and len(docs) >= max_docs:
                return docs
    return docs


def golden():
    ruta = RAIZ / "pruebas" / "golden.tsv"
    if not ruta.exists():
        return []
    salida = []
    for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        if linea and not linea.startswith("#") and not linea.startswith("perfil\t"):
            perfil, entrada, _ = linea.split("\t")
            salida.append((perfil, f"golden.tsv:{n}", entrada.replace("\\n", "\n")))
    return salida


def a_linea(texto):
    # Formato --lineas: "\n" literal representa un salto; una barra invertida seguida de n se protege.
    return texto.replace("\r", "").replace("\\n", "\\ n").replace("\n", "\\n")


def correr(cmd, textos):
    entrada = "".join(a_linea(t) + "\n" for t in textos).encode("utf-8")
    env = dict(os.environ, PYTHONPATH=str(RAIZ / "python"), PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, input=entrada, capture_output=True, env=env, shell=False)
    if r.returncode != 0:
        sys.exit(f"fallo {cmd[0]}:\n{r.stderr.decode('utf-8', 'replace')}")
    return r.stdout.decode("utf-8").split("\n")[:len(textos)]


def primera_diferencia(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x, y
    return min(len(a), len(b)), (a[len(b)] if len(a) > len(b) else None), (b[len(a)] if len(b) > len(a) else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpetas", nargs="*")
    ap.add_argument("--perfil", action="append", help="perfil(es) a probar; por defecto todos los de perfiles/")
    ap.add_argument("--max-docs", type=int, default=0)
    args = ap.parse_args()

    if not JAVA_BIN.exists():
        sys.exit(f"No existe {JAVA_BIN}. Compile primero: cd normalizacion/java && ./gradlew installDist")

    perfiles = args.perfil or sorted(p.stem for p in (RAIZ / "perfiles").glob("*.conf"))
    docs = documentos(args.carpetas or [RAIZ / "pruebas" / "muestra"], args.max_docs)
    casos_golden = golden()
    total_dif = 0
    for perfil in perfiles:
        conf = str(RAIZ / "perfiles" / f"{perfil}.conf")
        casos = docs + [(n, t) for p, n, t in casos_golden if p == perfil]
        textos = [t for _, t in casos]
        py = correr([sys.executable, "-m", "paleonorm", "--conf", conf, "--lineas"], textos)
        jv = correr([str(JAVA_BIN), "--conf", conf, "--lineas"], textos)
        dif = 0
        terminos = 0
        for (nombre, _), a, b in zip(casos, py, jv):
            ta, tb = a.split(), b.split()
            terminos += len(ta)
            if ta != tb:
                dif += 1
                i, x, y = primera_diferencia(ta, tb)
                print(f"  [{perfil}] {nombre}: termino #{i}: python={x!r} lucene={y!r}")
        estado = "IDENTICOS" if dif == 0 else f"{dif} DOCUMENTOS DISTINTOS"
        print(f"{perfil}: {len(casos)} documentos, {terminos} terminos -> {estado}")
        total_dif += dif
    sys.exit(1 if total_dif else 0)


if __name__ == "__main__":
    main()
