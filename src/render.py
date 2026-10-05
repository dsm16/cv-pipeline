"""
render.py — Fase 4 del pipeline.
Toma el master profile + una selección de bullets, y genera el PDF final,
en español, inglés, o ambos.

Uso:
    python src/render.py vacantes/prueba --lang es
    python src/render.py vacantes/prueba --lang en
    python src/render.py vacantes/prueba --lang both
"""

import argparse
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from playwright.sync_api import sync_playwright

from intake_common import ruta_pipeline
from config import MASTER_PATH

from labels import LABELS
from utils import formatear_fecha

# --- Rutas del proyecto (relativas a la raíz de cv-pipeline) ---
RAIZ = Path(__file__).parent.parent
TEMPLATE_DIR = RAIZ / "templates"


def cargar_yaml(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def campo(dic: dict, base: str, lang: str, etiqueta: str = "") -> str:
    """
    Elige el campo en el idioma pedido. Si piden inglés y no existe
    '<base>_en', hace fallback al español y avisa en consola —
    así nunca truena, pero tú sabes qué te falta traducir.
    """
    if lang == "en":
        valor_en = dic.get(f"{base}_en")
        if valor_en:
            return valor_en
        print(f"  [aviso] falta traducción '{base}_en' en {etiqueta or dic.get('id', '?')} — usando español")
    if base not in dic and base != "metrica":
        raise ValueError(f"Falta el campo '{base}' en {etiqueta or dic.get('id', '?')}")
    return dic.get(base, "")


def filtrar_experiencia(experiencia: list[dict], ids_seleccionados: list[str], lang: str) -> list[dict]:
    resultado = []
    for exp in experiencia:
        bullets_filtrados = []
        for b in exp["bullets"]:
            if b["id"] in ids_seleccionados:
                bullets_filtrados.append({
                    "accion": campo(b, "accion", lang, etiqueta=b["id"]),
                    "metrica": campo(b, "metrica", lang, etiqueta=b["id"]),
                })
        if bullets_filtrados:
            resultado.append({
                "puesto": campo(exp, "puesto", lang, etiqueta=exp["empresa"]),
                "empresa": exp["empresa"],  # nombres propios no se traducen
                "ubicacion": exp["ubicacion"],
                "fecha_inicio": formatear_fecha(exp["fecha_inicio"], lang),
                "fecha_fin": formatear_fecha(exp["fecha_fin"], lang),
                "bullets": bullets_filtrados,
            })
    return resultado


def formatear_educacion(educacion: list[dict], lang: str) -> list[dict]:
    return [{
        "titulo": campo(edu, "titulo", lang, etiqueta=edu["institucion"]),
        "institucion": edu["institucion"],
        "ubicacion": edu["ubicacion"],
        "fecha_inicio": formatear_fecha(edu["fecha_inicio"], lang),
        "fecha_fin": formatear_fecha(edu["fecha_fin"], lang),
    } for edu in educacion]


def formatear_skills(skills_tecnicas: list[dict], lang: str) -> list[dict]:
    resultado = []
    for cat in skills_tecnicas:
        # items_en es opcional: solo la pones si hay palabras que sí cambian
        # (ej. "Tokenización" -> "Tokenization"). Si no existe, se usa la lista tal cual.
        items = cat.get("items_en") if lang == "en" and cat.get("items_en") else cat["items"]
        resultado.append({
            "categoria": campo(cat, "categoria", lang, etiqueta="skills_tecnicas"),
            "items": items,
        })
    return resultado


def formatear_skills_blandas(master: dict, lang: str) -> list[str]:
    if lang == "en" and master.get("skills_blandas_en"):
        return master["skills_blandas_en"]
    return master.get("skills_blandas", [])


def filtrar_proyectos(proyectos: list[dict], nombres_seleccionados: list[str], lang: str) -> list[dict]:
    resultado = []
    for p in proyectos:
        if p["nombre"] in nombres_seleccionados:
            resultado.append({
                "nombre": p["nombre"],
                "texto": campo(p, "texto", lang, etiqueta=p["nombre"]),
            })
    return resultado


def buscar_resumen(resumenes: list[dict], resumen_id: str, lang: str) -> str:
    for r in resumenes:
        if r["id"] == resumen_id:
            return campo(r, "texto", lang, etiqueta=resumen_id).strip()
    raise ValueError(f"No encontré un resumen con id '{resumen_id}'")


def validar_seleccion(seleccion: dict, master: dict) -> None:
    """Reject missing or unknown references before generating any output."""
    if not isinstance(seleccion, dict):
        raise ValueError("La selección debe ser un objeto YAML.")
    resumen_id = seleccion.get("resumen_id")
    if not isinstance(resumen_id, str) or resumen_id not in {r["id"] for r in master["resumenes"]}:
        raise ValueError("La selección contiene un resumen_id inválido.")
    referencias = {
        "bullets_seleccionados": {b["id"] for exp in master["experiencia"] for b in exp["bullets"]},
        "proyectos_seleccionados": {p["nombre"] for p in master.get("proyectos", [])},
    }
    for campo_id, conocidos in referencias.items():
        valores = seleccion.get(campo_id, [] if campo_id == "proyectos_seleccionados" else None)
        if not isinstance(valores, list) or any(not isinstance(v, str) for v in valores):
            raise ValueError(f"'{campo_id}' debe ser una lista de texto.")
        if set(valores) - conocidos:
            raise ValueError(f"'{campo_id}' contiene referencias desconocidas.")


def crear_entorno() -> Environment:
    """Treat profile text as text and fail explicitly on template mistakes."""
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"], default_for_string=True),
        undefined=StrictUndefined,
    )


def renderizar_html(seleccion: dict, master: dict, lang: str) -> str:
    """Build HTML in memory; no browser or filesystem writes are required."""
    if lang not in LABELS:
        raise ValueError(f"Idioma no soportado: {lang}")
    validar_seleccion(seleccion, master)
    contexto = {
        "lang": lang,
        "labels": LABELS[lang],
        "nombre": master["datos_personales"]["nombre"],
        "titulo_profesional": campo(master["datos_personales"], "titulo_profesional", lang, etiqueta="datos_personales"),
        "email": master["datos_personales"]["email"],
        "telefono": master["datos_personales"]["telefono"],
        "ubicacion": master["datos_personales"]["ubicacion"],
        "linkedin": master["datos_personales"]["linkedin"],
        "resumen": buscar_resumen(master["resumenes"], seleccion["resumen_id"], lang),
        "experiencia": filtrar_experiencia(master["experiencia"], seleccion["bullets_seleccionados"], lang),
        "proyectos": filtrar_proyectos(master.get("proyectos", []), seleccion.get("proyectos_seleccionados", []), lang),
        "educacion": formatear_educacion(master["educacion"], lang),
        "skills_tecnicas": formatear_skills(master["skills_tecnicas"], lang),
        "skills_blandas": formatear_skills_blandas(master, lang),
        "idiomas": [
            f"{campo(i, 'idioma', lang, etiqueta='idiomas')} ({campo(i, 'nivel', lang, etiqueta='idiomas')})"
            for i in master["idiomas"]
        ],
        "css_path": (TEMPLATE_DIR / "cv.css").resolve().as_uri(),
    }

    env = crear_entorno()
    template = env.get_template("cv_template.html")
    return template.render(**contexto)


def renderizar_idioma(carpeta: Path, seleccion: dict, master: dict, lang: str):
    html_final = renderizar_html(seleccion, master, lang)

    html_path = ruta_pipeline(carpeta) / f"cv_{lang}.html"
    html_path.write_text(html_final, encoding="utf-8")

    pdf_path = carpeta / f"cv_{lang}.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri())
        page.pdf(path=str(pdf_path), format="A4", print_background=True)
        browser.close()

    print(f"PDF generado ({lang}): {pdf_path}")


def main(carpeta_vacante: str, lang: str):
    carpeta = Path(carpeta_vacante)
    seleccion = cargar_yaml(ruta_pipeline(carpeta) / "seleccion.yaml")
    master = cargar_yaml(MASTER_PATH)

    idiomas_a_generar = ["es", "en"] if lang == "both" else [lang]
    for idioma in idiomas_a_generar:
        renderizar_idioma(carpeta, seleccion, master, idioma)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera el CV en PDF a partir del master profile.")
    parser.add_argument("carpeta_vacante", help="Carpeta de la vacante, ej: vacantes/prueba")
    parser.add_argument("--lang", choices=["es", "en", "both"], default="es", help="Idioma del CV")
    args = parser.parse_args()
    main(args.carpeta_vacante, args.lang)
