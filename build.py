"""Genera el sitio de hojas de vida en _site/: portada, una página por persona y
un PDF de una hoja por persona y paleta (impresión compacta con Chrome sin interfaz).

Uso:
  python build.py              # HTML + PDF
  python build.py --sin-pdf    # solo HTML

Variables de entorno:
  CHROME   ruta del ejecutable de Chrome/Chromium (si no, se busca uno instalado)
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "_site"

PALETAS = [
    {"id": "ciruela", "nombre": "Ciruela", "tapa": "#3B1F35", "movimiento": "#A3335A"},
    {"id": "esmeralda", "nombre": "Esmeralda", "tapa": "#183D35", "movimiento": "#B8325C"},
    {"id": "medianoche", "nombre": "Medianoche", "tapa": "#1C2A4D", "movimiento": "#0E7A70"},
    {"id": "lavanda", "nombre": "Grafito y lavanda", "tapa": "#2B2A33", "movimiento": "#7A3FD1"},
    {"id": "petroleo", "nombre": "Petróleo y durazno", "tapa": "#0F3B47", "movimiento": "#C2305F"},
]

CHROME_CANDIDATOS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def pendientes(texto) -> Markup:
    """Escapa el texto y marca los [datos pendientes] para que se vean subrayados."""
    seguro = str(escape(str(texto)))
    return Markup(re.sub(r"\[([^\]]+)\]", r'<span class="pendiente">[\1]</span>', seguro))


def cargar_personas() -> list[dict]:
    personas = []
    for archivo in sorted((RAIZ / "datos").glob("*.yaml")):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        if datos.get("publicar", True) is False:
            print(f"OMITIDA  {archivo.name} (publicar: false)")
            continue
        datos["tiene_enlaces"] = any(
            x.get("enlace") for x in datos.get("educacion", []) + datos.get("formacion", []))
        datos["pendientes"] = len(re.findall(r"\[[^\]]+\]", archivo.read_text(encoding="utf-8")))
        personas.append(datos)
    return personas


def buscar_chrome() -> str:
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for ruta in CHROME_CANDIDATOS:
        if Path(ruta).exists():
            return ruta
    for nombre in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        if shutil.which(nombre):
            return shutil.which(nombre)
    sys.exit("No encontré Chrome. Define la variable de entorno CHROME.")


def generar_pdf(chrome: str, html: Path, paleta: str, destino: Path) -> None:
    url = html.resolve().as_uri() + f"?paleta={paleta}"
    subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
         "--run-all-compositor-stages-before-draw", "--virtual-time-budget=4000",
         f"--print-to-pdf={destino}", url],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


def paginas_pdf(ruta: Path) -> int:
    from pypdf import PdfReader
    return len(PdfReader(str(ruta)).pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-pdf", action="store_true")
    args = ap.parse_args()

    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    shutil.copytree(RAIZ / "assets", SALIDA / "assets")
    (SALIDA / ".nojekyll").write_text("", encoding="utf-8")

    env = Environment(loader=FileSystemLoader(RAIZ / "plantillas"),
                      autoescape=select_autoescape(["html", "j2"]))
    env.filters["pend"] = pendientes

    personas = cargar_personas()
    (SALIDA / "index.html").write_text(
        env.get_template("portada.html.j2").render(personas=personas), encoding="utf-8")

    plantilla = env.get_template("cv.html.j2")
    for p in personas:
        carpeta = SALIDA / p["slug"]
        carpeta.mkdir(parents=True)
        (carpeta / "index.html").write_text(plantilla.render(p=p, paletas=PALETAS), encoding="utf-8")
        aviso = f"  ({p['pendientes']} datos pendientes entre corchetes)" if p["pendientes"] else ""
        print(f"HTML  {p['slug']}/index.html{aviso}")

    if args.sin_pdf:
        return

    chrome = buscar_chrome()
    (SALIDA / "pdf").mkdir()
    errores = []
    for p in personas:
        for pal in PALETAS:
            destino = SALIDA / "pdf" / f"{p['slug']}-{pal['id']}.pdf"
            generar_pdf(chrome, SALIDA / p["slug"] / "index.html", pal["id"], destino)
            n = paginas_pdf(destino)
            print(f"PDF   {destino.name}: {n} página(s)")
            if n != 1:
                errores.append(f"{destino.name} tiene {n} páginas; debe ser 1")
    if errores:
        sys.exit("\n".join(errores))


if __name__ == "__main__":
    main()
