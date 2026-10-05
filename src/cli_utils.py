"""
cli_utils.py — utilidades compartidas para menús interactivos por consola.

Toda decisión del usuario en el pipeline se hace con números (1, 2, 3...),
nunca escribiendo texto libre como 's'/'n' o 'es'/'en' — así no dependes
de acordarte de comandos exactos, solo lees y eliges un número.
"""


def elegir_opcion(pregunta: str, opciones: list[str]) -> int:
    """
    Muestra una pregunta con opciones numeradas y devuelve el número
    elegido (empezando en 1). Repite la pregunta si escriben algo inválido,
    así el programa nunca truena por una respuesta inesperada.
    """
    print(f"\n{pregunta}")
    for i, opcion in enumerate(opciones, start=1):
        print(f"  {i}) {opcion}")

    while True:
        respuesta = input(f"Elige una opción [1-{len(opciones)}]: ").strip()
        if respuesta.isdigit() and 1 <= int(respuesta) <= len(opciones):
            return int(respuesta)
        print(f"  Opción inválida. Escribe un número del 1 al {len(opciones)}.")


def elegir_idioma() -> str:
    """Menú numerado para elegir idioma del CV. Devuelve 'es', 'en' o 'both'."""
    opcion = elegir_opcion(
        "¿En qué idioma quieres el CV?",
        ["Español", "Inglés", "Ambos (español e inglés)"],
    )
    return {1: "es", 2: "en", 3: "both"}[opcion]