"""
utils.py — funciones reutilizables del pipeline.
"""

import re


def contiene_keyword(texto: str, keyword: str) -> bool:
    """Literal, case-insensitive match, including keywords such as C++/C#.

    Word characters and +/# cannot adjoin a match. This prevents SQL inside
    MySQLite and C inside C++, while accepting punctuation around a keyword.
    """
    if not keyword.strip():
        return False
    patron = r"(?<![\w+#])" + re.escape(keyword.lower()) + r"(?![\w+#])"
    return re.search(patron, texto.lower()) is not None


def normalize_tag(tag: str) -> str:
    """
    Normaliza un tag individual: minúsculas y sin espacios extra.
    'APIs' -> 'apis' | ' Python ' -> 'python'
    """
    return tag.strip().lower()


def normalize_tags(tags: list[str]) -> set[str]:
    """
    Normaliza una lista de tags y elimina duplicados.
    Usamos un set (conjunto) porque no importa el orden y
    las comparaciones de "¿este tag está en esta lista?" son más rápidas.
    """
    return {normalize_tag(t) for t in tags}


def tags_overlap(tags_a: list[str], tags_b: list[str]) -> set[str]:
    """
    Devuelve los tags en común entre dos listas, ya normalizados.
    Esto es lo que usaremos en la Fase 3 (matching) para saber
    qué tan afín es un bullet del master profile a una vacante.
    """
    return normalize_tags(tags_a) & normalize_tags(tags_b)


if __name__ == "__main__":
    # Esto solo se ejecuta si corres "python utils.py" directamente,
    # no cuando lo importas desde otro script. Sirve para probar rápido.
    a = ["APIs", "Python", "automatizacion"]
    b = ["apis", "SQL", "Automatizacion"]
    print("Tags A normalizados:", normalize_tags(a))
    print("Tags en común:", tags_overlap(a, b))


MESES = {
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio",
           "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
}

# Palabras clave especiales que no son fechas reales (trabajo actual, estudios en curso)
ESPECIALES = {
    "presente": {"es": "Presente", "en": "Present"},
    "cursando": {"es": "Cursando", "en": "In progress"},
}


def formatear_fecha(valor: str, lang: str) -> str:
    """
    Convierte una fecha guardada en formato neutro a texto legible
    en el idioma pedido.
    Formatos aceptados en el YAML:
      "2025-09"  -> "septiembre 2025" (es) / "September 2025" (en)
      "2025"     -> "2025" (los años no cambian entre idiomas)
      "presente" / "cursando" -> se traducen desde ESPECIALES
    """
    valor = str(valor).strip()

    if lang not in MESES:
        raise ValueError(f"Idioma no soportado: {lang}")

    if valor.lower() in ESPECIALES:
        return ESPECIALES[valor.lower()][lang]

    if re.match(r"^\d{4}-", valor):
        if not re.fullmatch(r"\d{4}-\d{2}", valor):
            raise ValueError(f"Fecha inválida; usa AAAA-MM: {valor}")
        anio, mes = valor.split("-")
        if int(anio) < 1 or not 1 <= int(mes) <= 12:
            raise ValueError(f"Fecha inválida: {valor}")
        nombre_mes = MESES[lang][int(mes) - 1]
        return f"{nombre_mes} {anio}"

    return valor  # solo año u otro formato: se muestra tal cual
