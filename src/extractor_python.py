"""
extractor_python.py — implementación del extractor de requisitos usando
solo reglas de Python (regex), sin llamadas a ningún servicio externo.

Todo extractor del pipeline debe exponer una función con esta misma firma:
    extraer(texto: str, keywords_conocidas: list[str]) -> dict

Eso es lo que permite intercambiarlos en parser.py sin tocar el resto
del pipeline: el día que quieras probar Gemini, DeepSeek, etc., creas
extractor_gemini.py con una función 'extraer' igual de forma, y la
registras en EXTRACTORES dentro de parser.py.
"""

import re

from utils import contiene_keyword


def extraer(texto: str, keywords_conocidas: list[str]) -> dict:
    texto_lower = texto.lower()

    keywords_detectadas = []
    for kw in keywords_conocidas:
        if contiene_keyword(texto_lower, kw):
            keywords_detectadas.append(kw)

    anios_match = re.search(r"(\d+)\s*(?:\+)?\s*años?\s+de\s+experiencia", texto_lower)
    anios_experiencia_min = int(anios_match.group(1)) if anios_match else None

    return {
        "keywords_detectadas": sorted(set(keywords_detectadas)),
        "anios_experiencia_min": anios_experiencia_min,
    }
