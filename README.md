# Hojas de vida

Sitio estático con las hojas de vida de Daniel Galvis y Valentina Araujo: cinco paletas de color en pantalla y un PDF de una sola hoja por paleta para descargar.

## Cómo funciona

- `datos/<persona>.yaml`: todo el contenido de cada hoja de vida. Es lo único que se edita para actualizarla.
- `plantillas/`: HTML con Jinja2 (`cv.html.j2` para cada persona, `portada.html.j2` para la entrada).
- `assets/css/cv.css`: un solo estilo con dos presentaciones. En pantalla es amplia y adaptable al celular; al imprimir (`@media print`) es compacta y cabe en una hoja carta.
- `build.py`: genera `_site/` con la portada, una página por persona y `pdf/<persona>-<paleta>.pdf`, impresos con Chrome sin interfaz. **Falla si algún PDF ocupa más de una hoja.**
- `.github/workflows/publicar.yml`: en cada push a `main` construye el sitio y lo publica en GitHub Pages.

## Uso local

```bash
pip install -r requirements.txt
python build.py            # HTML + PDF (necesita Chrome; o define CHROME=/ruta/al/chrome)
python build.py --sin-pdf  # solo HTML
python -m http.server -d _site 8000
```

## Reglas del contenido

- Los textos entre `[corchetes]` son datos pendientes: se ven subrayados y no deben publicarse así.
- `publicar: false` en el YAML de una persona la deja fuera del sitio.
- Ninguna cifra o logro sin respaldo: el contenido sale de la base de conocimiento privada de cada persona.

Tipografía: Figtree (SIL Open Font License).
