"""Genera el sitio de hojas de vida en _site/: portada, una página por persona,
un PDF visual de una hoja por persona y paleta, un PDF para ATS por persona y las
vistas previas e imágenes para compartir (Open Graph).

Uso:
  python build.py               # sitio completo (falla ante cualquier problema)
  python build.py --sin-pdf     # solo HTML
  python build.py --borradores  # incluye a las personas con publicar: false (solo local)

Variables de entorno:
  CHROME   ruta del ejecutable de Chrome/Chromium (si no, se busca uno instalado)
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "_site"
URL_BASE = "https://danielgalvis-dev.github.io/cv"

PALETAS = [
    {"id": "ciruela", "nombre": "Ciruela", "tapa": "#3B1F35", "movimiento": "#A3335A", "claro": "#F4C6D6", "texto": "#E8D6E0"},
    {"id": "esmeralda", "nombre": "Esmeralda", "tapa": "#183D35", "movimiento": "#B8325C", "claro": "#F5B8C9", "texto": "#DCEBE3"},
    {"id": "medianoche", "nombre": "Medianoche", "tapa": "#1C2A4D", "movimiento": "#0E7A70", "claro": "#8FE0D5", "texto": "#DCE2F2"},
    {"id": "lavanda", "nombre": "Grafito y lavanda", "tapa": "#2B2A33", "movimiento": "#7A3FD1", "claro": "#CDB5F5", "texto": "#E7E5EE"},
    {"id": "petroleo", "nombre": "Petróleo y durazno", "tapa": "#0F3B47", "movimiento": "#C2305F", "claro": "#FFB8A1", "texto": "#D9EBEE"},
]
IDS_PALETAS = {p["id"] for p in PALETAS}
OBLIGATORIOS = ("slug", "nombre", "rol", "archivo", "foto", "paleta", "contacto", "perfil", "experiencia", "educacion")
ENCABEZADOS_ATS = ("Perfil", "Experiencia", "Educación", "Habilidades")

CHROME_CANDIDATOS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


class ErrorDatos(Exception):
    pass


def pendientes(texto) -> Markup:
    """Escapa el texto y marca los [datos pendientes] para que se vean subrayados."""
    seguro = str(escape(str(texto)))
    return Markup(re.sub(r"\[([^\]]+)\]", r'<span class="pendiente">[\1]</span>', seguro))


def textos(valor):
    """Recorre todos los textos de un dato cargado (para contar pendientes sin comentarios)."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from textos(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from textos(v)


def validar(datos, archivo: str) -> None:
    if not isinstance(datos, dict):
        raise ErrorDatos(f"{archivo}: el YAML está vacío o no es un mapa")
    faltan = [c for c in OBLIGATORIOS if not datos.get(c)]
    if faltan:
        raise ErrorDatos(f"{archivo}: faltan campos obligatorios: {', '.join(faltan)}")
    if not re.fullmatch(r"[a-z0-9-]+", str(datos["slug"])):
        raise ErrorDatos(f"{archivo}: slug inválido '{datos['slug']}' (solo minúsculas, números y guiones)")
    datos["formacion"] = datos.get("formacion") or []
    for campo in ("experiencia", "educacion", "formacion", "idiomas", "tapa"):
        valor = datos.get(campo) or []
        if not isinstance(valor, list) or not all(isinstance(x, dict) for x in valor):
            raise ErrorDatos(f"{archivo}: '{campo}' debe ser una lista de entradas con campos (no texto suelto)")
    if datos["paleta"] not in IDS_PALETAS:
        raise ErrorDatos(f"{archivo}: paleta '{datos['paleta']}' no existe ({', '.join(sorted(IDS_PALETAS))})")
    if not (RAIZ / "assets" / "img" / datos["foto"]).exists():
        raise ErrorDatos(f"{archivo}: no existe la foto assets/img/{datos['foto']}")
    for e in datos["experiencia"]:
        for punto in e.get("puntos", []):
            if isinstance(punto, dict) and "texto" not in punto:
                raise ErrorDatos(f"{archivo}: viñeta mal formada en '{e.get('cargo')}': {punto}. "
                                 "Si la frase lleva ': ' (dos puntos y espacio), ponla entre comillas.")
    for item in datos["educacion"] + datos["formacion"]:
        enlace = item.get("enlace")
        if enlace and not str(enlace).startswith("https://"):
            raise ErrorDatos(f"{archivo}: enlace no seguro en '{item.get('titulo')}': {enlace}")


def cargar_personas(borradores: bool) -> list[dict]:
    personas, slugs = [], set()
    for archivo in sorted((RAIZ / "datos").glob("*.yaml")):
        try:
            datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ErrorDatos(f"{archivo.name}: YAML mal formado: {e}") from e
        validar(datos, archivo.name)
        if datos.get("publicar", True) is False and not borradores:
            print(f"OMITIDA  {archivo.name} (publicar: false)")
            continue
        if datos["slug"] in slugs:
            raise ErrorDatos(f"{archivo.name}: slug repetido '{datos['slug']}'")
        slugs.add(datos["slug"])
        datos["tiene_enlaces"] = any(x.get("enlace") for x in datos["educacion"] + datos["formacion"])
        datos["pendientes"] = sum(len(re.findall(r"\[[^\]]+\]", t)) for t in textos(datos))
        datos["es_borrador"] = datos.get("publicar", True) is False
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


def generar_pdf(chrome: str, html: Path, paleta: str | None, destino: Path) -> None:
    url = html.resolve().as_uri() + (f"?paleta={paleta}" if paleta else "")
    r = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
         "--run-all-compositor-stages-before-draw", "--virtual-time-budget=4000",
         f"--print-to-pdf={destino}", url],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not destino.exists() or destino.stat().st_size == 0:
        raise RuntimeError(f"Chrome no generó {destino.name} (código {r.returncode}):\n{r.stderr[-1500:]}")


def leer_pdf(ruta: Path) -> tuple[int, str, list[str]]:
    """Páginas, texto extraído (como un ATS) y tipos de fuente incrustados."""
    import pymupdf
    from pypdf import PdfReader
    doc = pymupdf.open(str(ruta))
    tipos = sorted({f[2] for pagina in doc for f in pagina.get_fonts()})
    texto = "\n".join(pg.extract_text() or "" for pg in PdfReader(str(ruta)).pages)
    return len(doc), texto, tipos


def revisar_pdf(ruta: Path, persona: dict, ats: bool) -> list[str]:
    """Lectura tipo ATS. En la versión ATS se exige todo; en la visual, orden y fuentes."""
    paginas, texto, tipos = leer_pdf(ruta)
    problemas = []
    if paginas != 1:
        problemas.append(f"tiene {paginas} páginas; debe ser 1")
    if "Type3" in tipos:
        problemas.append("usa fuentes Type3 (algunos ATS no las leen)")
    if any(0xE000 <= ord(ch) <= 0xF8FF or ch == "\ufffd" for ch in texto):
        problemas.append("hay caracteres ilegibles")
    # Orden de lectura: el primer logro debe leerse antes que la sección Educación.
    primero = next((pt["texto"] if isinstance(pt, dict) else pt
                    for e in persona["experiencia"] if e.get("en_pdf", True) is not False
                    for pt in e.get("puntos", [])
                    if not (isinstance(pt, dict) and pt.get("en_pdf") is False)), None)
    if primero:
        inicio = re.sub(r"\s+", " ", primero)[:40]
        plano = re.sub(r"\s+", " ", texto)
        if inicio not in plano:
            problemas.append("no se encontró el primer logro en el texto extraído (revisar orden de lectura)")
        elif plano.find(inicio) > plano.find("Educación"):
            problemas.append("orden de lectura roto: los logros aparecen después de Educación")
    if ats:
        lineas = {l.strip() for l in texto.splitlines()}
        if not texto.lstrip().startswith(persona["nombre"]):
            problemas.append("el nombre no es lo primero que se lee")
        contacto = persona["contacto"]
        if contacto.get("correo") and contacto["correo"] not in texto:
            problemas.append("no se detecta el correo")
        if contacto.get("telefono") and not re.search(r"\+\d[\d ]{7,}", texto):
            problemas.append("no se detecta el teléfono con indicativo")
        for seccion in ENCABEZADOS_ATS:
            if seccion not in lineas:
                problemas.append(f"falta el encabezado '{seccion}' como línea propia")
    if not persona["es_borrador"] and re.search(r"\[[^\]]+\]", texto):
        problemas.append("contiene [datos pendientes]")
    return problemas


def generar_vista(pdf: Path, destino: Path) -> None:
    """Imagen de la primera página para la vista previa antes de descargar."""
    import pymupdf
    from PIL import Image
    pix = pymupdf.open(str(pdf))[0].get_pixmap(dpi=80)
    Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(destino, quality=82, optimize=True)


def generar_og(persona: dict, destino: Path) -> None:
    """Tarjeta 1200x630 para compartir el enlace (WhatsApp, LinkedIn): foto, nombre y rol."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    pal = next(p for p in PALETAS if p["id"] == persona["paleta"])
    lienzo = Image.new("RGB", (1200, 630), pal["tapa"])
    d = ImageDraw.Draw(lienzo)
    negrita = ImageFont.truetype(str(RAIZ / "recursos" / "Figtree-Bold.ttf"), 64)
    normal = ImageFont.truetype(str(RAIZ / "recursos" / "Figtree-Regular.ttf"), 30)
    foto = ImageOps.fit(Image.open(RAIZ / "assets" / "img" / persona["foto"]).convert("RGB"),
                        (320, 320), centering=(0.5, 0.25))
    mascara = Image.new("L", (320, 320), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, 320, 320), fill=255)
    d.ellipse((72, 147, 408, 483), fill=pal["claro"])
    lienzo.paste(foto, (80, 155), mascara)

    def partir(texto, fuente, ancho):
        lineas, actual = [], ""
        for palabra in texto.split():
            prueba = (actual + " " + palabra).strip()
            if d.textlength(prueba, font=fuente) <= ancho:
                actual = prueba
            else:
                lineas.append(actual)
                actual = palabra
        return lineas + [actual]

    y = 170
    for linea in partir(persona["nombre"], negrita, 680)[:3]:
        d.text((470, y), linea, font=negrita, fill="#FFFFFF")
        y += 74
    y += 18
    for linea in partir(re.sub(r"\[[^\]]+\]", "", persona["rol"]), normal, 680)[:3]:
        d.text((470, y), linea, font=normal, fill=pal["texto"])
        y += 40
    d.text((470, 540), "Hoja de vida", font=normal, fill=pal["claro"])
    lienzo.save(destino, quality=86, optimize=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-pdf", action="store_true")
    ap.add_argument("--borradores", action="store_true",
                    help="incluye personas con publicar: false (no usar para publicar)")
    args = ap.parse_args()

    try:
        personas = cargar_personas(args.borradores)
    except ErrorDatos as e:
        sys.exit(f"ERROR DE DATOS  {e}")

    # Se vacía el contenido en vez de borrar la carpeta: en Windows una carpeta abierta
    # por otro proceso (terminal, explorador) no se puede borrar, pero sí vaciar.
    SALIDA.mkdir(exist_ok=True)
    for hijo in SALIDA.iterdir():
        shutil.rmtree(hijo) if hijo.is_dir() else hijo.unlink()
    # Solo se copian las fotos de las personas que se publican (privacidad de los borradores).
    fotos = {p["foto"] for p in personas}
    def ignorar(carpeta, nombres):
        if Path(carpeta).name != "img":
            return []
        return [n for n in nombres if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and n not in fotos]
    shutil.copytree(RAIZ / "assets", SALIDA / "assets", ignore=ignorar)
    (SALIDA / ".nojekyll").write_text("", encoding="utf-8")

    env = Environment(loader=FileSystemLoader(RAIZ / "plantillas"),
                      autoescape=select_autoescape(["html", "j2"]))
    env.filters["pend"] = pendientes
    comunes = {"paletas": PALETAS, "url_base": URL_BASE}

    (SALIDA / "index.html").write_text(
        env.get_template("portada.html.j2").render(personas=personas, **comunes), encoding="utf-8")

    plantilla = env.get_template("cv.html.j2")
    for p in personas:
        carpeta = SALIDA / p["slug"]
        carpeta.mkdir(parents=True)
        defecto = next(x for x in PALETAS if x["id"] == p["paleta"])
        (carpeta / "index.html").write_text(
            plantilla.render(p=p, paleta_defecto=defecto, **comunes), encoding="utf-8")
        generar_og(p, SALIDA / "assets" / "img" / f"og-{p['slug']}.jpg")
        aviso = f"  ({p['pendientes']} datos pendientes entre corchetes)" if p["pendientes"] else ""
        print(f"HTML  {p['slug']}/index.html{aviso}")

    errores = [f"{p['slug']}: tiene {p['pendientes']} [datos pendientes] y está marcada para publicar"
               for p in personas if p["pendientes"] and not p["es_borrador"]]

    if args.sin_pdf:
        if errores:
            sys.exit("\n".join(errores))
        return

    chrome = buscar_chrome()
    (SALIDA / "pdf").mkdir()
    for p in personas:
        for pal in PALETAS:
            destino = SALIDA / "pdf" / f"{p['slug']}-{pal['id']}.pdf"
            generar_pdf(chrome, SALIDA / p["slug"] / "index.html", pal["id"], destino)
            problemas = revisar_pdf(destino, p, ats=False)
            print(f"PDF   {destino.name}: {'correcto' if not problemas else '; '.join(problemas)}")
            errores += [f"{destino.name}: {x}" for x in problemas]

    # Versión ATS: solo PDF. Su HTML se arma en una carpeta temporal y no se publica.
    plantilla_ats = env.get_template("ats.html.j2")
    fuentes = (RAIZ / "assets" / "fonts").resolve().as_uri()
    with tempfile.TemporaryDirectory(prefix="ats_") as temporal:
        for p in personas:
            html = Path(temporal) / f"{p['slug']}.html"
            html.write_text(plantilla_ats.render(p=p, fuentes=fuentes), encoding="utf-8")
            destino = SALIDA / "pdf" / f"{p['slug']}-ats.pdf"
            generar_pdf(chrome, html, None, destino)
            problemas = revisar_pdf(destino, p, ats=True)
            print(f"ATS   {destino.name}: {'lectura ATS correcta' if not problemas else '; '.join(problemas)}")
            errores += [f"{destino.name}: {x}" for x in problemas]

    vistas = SALIDA / "pdf" / "vistas"
    vistas.mkdir()
    for pdf in sorted((SALIDA / "pdf").glob("*.pdf")):
        generar_vista(pdf, vistas / f"{pdf.stem}.jpg")
    print(f"VISTA {len(list(vistas.glob('*.jpg')))} vistas previas")

    if errores:
        sys.exit("\n".join(errores))


if __name__ == "__main__":
    main()
