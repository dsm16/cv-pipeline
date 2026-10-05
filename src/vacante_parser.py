"""
parser.py — Fase 2 del pipeline.
Lee el texto de una vacante (metadata simple + descripción) y genera
un JSON normalizado que la Fase 3 (matching) va a consumir.

Formato esperado en vacantes/{carpeta}/raw.txt:

    TITULO: Analista de Datos Senior
    EMPRESA: Acme Corp
    UBICACION: CDMX (Híbrido)
    MODALIDAD: Híbrido
    ---
    [descripción completa de la vacante, texto libre]

Uso:
    python src/parser.py vacantes/prueba
    python src/parser.py vacantes/prueba --extractor python
"""

import argparse
import json
from pathlib import Path

import yaml

from extractor_python import extraer as extraer_python
from config import MASTER_PATH
from intake_common import ruta_pipeline

# Registro de extractores disponibles. Para agregar uno nuevo (ej. Gemini):
#   from extractor_gemini import extraer as extraer_gemini
#   EXTRACTORES["gemini"] = extraer_gemini
# El resto de este archivo no cambia.
EXTRACTORES = {
    "python": extraer_python,
}

RAIZ = Path(__file__).parent.parent


def cargar_keywords_conocidas() -> list[str]:
    """Aplana el banco de palabras_clave_ats del master profile en una sola lista."""
    with open(MASTER_PATH, encoding="utf-8") as f:
        master = yaml.safe_load(f)
    banco = master.get("palabras_clave_ats", {})
    todas = []
    for lista in banco.values():
        todas.extend(lista)
    return todas


def parsear_metadata(texto_crudo: str) -> tuple[dict, str]:
    """Separa el encabezado (TITULO:, EMPRESA:, ...) de la descripción, usando '---'."""
    if "---" not in texto_crudo:
        raise ValueError("raw.txt debe tener un separador '---' entre metadata y descripción.")

    encabezado, descripcion = texto_crudo.split("---", 1)
    metadata = {}
    for linea in encabezado.strip().splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            metadata[clave.strip().lower()] = valor.strip()
    return metadata, descripcion.strip()


def main(carpeta_vacante: str, nombre_extractor: str):
    carpeta = Path(carpeta_vacante)
    texto_crudo = (ruta_pipeline(carpeta) / "raw.txt").read_text(encoding="utf-8")

    metadata, descripcion = parsear_metadata(texto_crudo)
    keywords_conocidas = cargar_keywords_conocidas()

    extraer = EXTRACTORES[nombre_extractor]
    resultado = extraer(descripcion, keywords_conocidas)

    parsed = {
        "titulo": metadata.get("titulo", ""),
        "empresa": metadata.get("empresa", ""),
        "ubicacion": metadata.get("ubicacion", ""),
        "modalidad": metadata.get("modalidad", ""),
        **resultado,
        "extractor_usado": nombre_extractor,
    }

    out_path = ruta_pipeline(carpeta) / "parsed.json"
    out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"JSON generado: {out_path}")
    print(f"Keywords detectadas ({len(parsed['keywords_detectadas'])}): {parsed['keywords_detectadas']}")
    if parsed["anios_experiencia_min"] is not None:
        print(f"Años de experiencia mínimos detectados: {parsed['anios_experiencia_min']}")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Parsea el texto de una vacante a JSON normalizado.")
    cli.add_argument("carpeta_vacante", help="Carpeta de la vacante, ej: vacantes/prueba")
    cli.add_argument("--extractor", choices=list(EXTRACTORES.keys()), default="python")
    args = cli.parse_args()
    main(args.carpeta_vacante, args.extractor)
