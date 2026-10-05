"""
qa.py — Fase 5 del pipeline.
Valida el/los CV(s) ya generados: cobertura de keywords de la vacante,
número de páginas, y señales de errores de plantilla. Todo con Python
puro (pdfplumber lee el PDF tal como quedó), sin ninguna llamada a IA.

Uso:
    python src/qa.py vacantes/nombre_carpeta
"""

import argparse
import json
from pathlib import Path

import pdfplumber

from intake_common import ruta_pipeline
from utils import contiene_keyword

RAIZ = Path(__file__).parent.parent


def extraer_texto_pdf(pdf_path: Path) -> tuple[str, int]:
    """Devuelve (texto completo del PDF, número de páginas)."""
    partes = []
    with pdfplumber.open(pdf_path) as pdf:
        n_paginas = len(pdf.pages)
        for pagina in pdf.pages:
            partes.append(pagina.extract_text() or "")
    return "\n".join(partes), n_paginas


def calcular_cobertura(texto_pdf: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    """Compara, sin distinguir mayúsculas, qué keywords de la vacante sí
    aparecen en el texto del PDF y cuáles no."""
    texto_lower = texto_pdf.lower()
    encontradas, faltantes = [], []
    for kw in keywords:
        (encontradas if contiene_keyword(texto_lower, kw) else faltantes).append(kw)
    return encontradas, faltantes


def revisar_placeholders(texto_pdf: str) -> list[str]:
    """Detecta si quedó algún '{{ }}' de Jinja2 sin llenar — señal de un
    bug en el render que de otra forma pasaría desapercibido en el PDF."""
    problemas = []
    if "{{" in texto_pdf or "}}" in texto_pdf:
        problemas.append("Se encontraron placeholders de plantilla sin llenar ({{ }}) — revisa el render.")
    return problemas


def clasificar_afinidad(pct: float) -> str:
    """Traduce el % de cobertura de keywords a un veredicto legible."""
    if pct >= 80:
        return "Excelente match — tu CV cubre casi todo lo que pide la vacante"
    if pct >= 60:
        return "Buen match — cubres la mayoría de lo importante"
    if pct >= 40:
        return "Match moderado — revisa las keywords faltantes, quizá falte tag o contenido"
    return "Match bajo — o te falta ampliar keyword_tag_map, o esta vacante no es muy afín a tu perfil real"


def generar_reporte(carpeta: Path) -> str:
    """Arma el reporte QA completo como texto (para imprimir y para guardar en archivo)."""
    pipeline_dir = ruta_pipeline(carpeta)

    keywords = []
    parsed_path = pipeline_dir / "parsed.json"
    if parsed_path.exists():
        with open(parsed_path, encoding="utf-8") as f:
            keywords = json.load(f).get("keywords_detectadas", [])

    pdfs = sorted(carpeta.glob("cv_*.pdf"))
    lineas = [f"REPORTE QA — {carpeta.name}"]

    if not pdfs:
        lineas.append("No se encontró ningún PDF en esta carpeta. Corre render.py primero.")
        return "\n".join(lineas)

    porcentajes = []
    detalle_pdfs = []

    for pdf_path in pdfs:
        texto, n_paginas = extraer_texto_pdf(pdf_path)
        lineas.append(f"\n--- {pdf_path.name} ---")

        aviso_paginas = "  [aviso] considera acortar, ideal 1-2 páginas" if n_paginas > 2 else ""
        lineas.append(f"Páginas: {n_paginas}{aviso_paginas}")

        for problema in revisar_placeholders(texto):
            lineas.append(f"  [ERROR] {problema}")

        if keywords:
            encontradas, faltantes = calcular_cobertura(texto, keywords)
            cobertura_pct = round(100 * len(encontradas) / len(keywords), 1)
            porcentajes.append(cobertura_pct)
            lineas.append(f"Cobertura de keywords de la vacante: {cobertura_pct}% ({len(encontradas)}/{len(keywords)})")
            if faltantes:
                lineas.append(f"  Keywords de la vacante que NO aparecen en este CV: {faltantes}")
        else:
            lineas.append("  (no hay parsed.json con keywords para comparar — ¿es un CV Full?)")

    if porcentajes:
        afinidad = round(sum(porcentajes) / len(porcentajes))
        veredicto = clasificar_afinidad(afinidad)
        encabezado_afinidad = [
            f"AFINIDAD_{afinidad}",
            veredicto,
            "=" * 50,
        ]
        lineas = [lineas[0]] + encabezado_afinidad + lineas[1:]
    else:
        lineas.insert(1, "=" * 50)

    lineas.append("\n" + "=" * 50)
    lineas.append(
        "Nota: el % de cobertura no es un veredicto de aprobado/reprobado. Revisa\n"
        "cuáles keywords faltan — si describen algo que sí sabes hacer, probablemente\n"
        "falte tag en el bullet correspondiente o una entrada en keyword_tag_map.\n"
        "Si describen algo que de verdad no has hecho, está bien que no aparezca."
    )
    return "\n".join(lineas)


def main(carpeta_vacante: str):
    carpeta = Path(carpeta_vacante)
    reporte = generar_reporte(carpeta)

    print(f"\n{reporte}\n")

    reporte_path = carpeta / "reporte_qa.txt"
    reporte_path.write_text(reporte, encoding="utf-8")
    print(f"Reporte guardado en: {reporte_path}")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="QA del CV generado: cobertura de keywords y checks de formato.")
    cli.add_argument("carpeta_vacante", help="Carpeta de la vacante, ej: vacantes/prueba")
    args = cli.parse_args()
    main(args.carpeta_vacante)
