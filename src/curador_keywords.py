"""
curador_keywords.py — herramienta interactiva (sin IA) para ampliar
keyword_tag_map poco a poco.

Revisa TODAS las vacantes que ya capturaste, junta las keywords que el
parser detectó en cada una, y te pregunta —una por una, con un menú
numerado de tus tags existentes— cuáles todavía no están mapeadas.

No modifica tu perfil.yaml directamente (para no arriesgar el formato
que ya tienes). Al final te entrega un bloque de YAML listo para pegar
tú mismo dentro de keyword_tag_map, y guarda tus decisiones de "ignorar"
en un archivo aparte para no volver a preguntarte por esas.

Uso:
    python src/curador_keywords.py
"""

import json
from pathlib import Path

import yaml

from cli_utils import elegir_opcion
from config import MASTER_PATH
from intake_common import _slug
from matcher import recolectar_tags_conocidos

RAIZ = Path(__file__).parent.parent
VACANTES_DIR = RAIZ / "vacantes"
IGNORADAS_PATH = RAIZ / "master" / "keywords_ignoradas.txt"
SUGERENCIAS_PATH = RAIZ / "master" / "_sugerencias_keyword_tag_map.yaml"


def cargar_master() -> dict:
    with open(MASTER_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def cargar_ignoradas() -> set[str]:
    if not IGNORADAS_PATH.exists():
        return set()
    return {linea.strip() for linea in IGNORADAS_PATH.read_text(encoding="utf-8").splitlines() if linea.strip()}


def guardar_ignorada(keyword: str) -> None:
    IGNORADAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(IGNORADAS_PATH, "a", encoding="utf-8") as f:
        f.write(keyword + "\n")


def recolectar_keywords_vistas() -> set[str]:
    """Junta las keywords_detectadas de TODAS las vacantes ya capturadas."""
    vistas = set()
    for parsed_path in VACANTES_DIR.glob("*/_pipeline/parsed.json"):
        try:
            with open(parsed_path, encoding="utf-8") as f:
                data = json.load(f)
            vistas.update(data.get("keywords_detectadas", []))
        except (json.JSONDecodeError, OSError):
            continue
    return vistas


def encontrar_sin_mapear(keywords: set[str], master: dict, ignoradas: set[str]) -> list[str]:
    keyword_map = master.get("keyword_tag_map", {})
    tags_conocidos = recolectar_tags_conocidos(master)

    sin_mapear = []
    for kw in sorted(keywords):
        if kw in ignoradas or kw in keyword_map:
            continue
        if _slug(kw) in tags_conocidos:
            continue
        sin_mapear.append(kw)
    return sin_mapear


def main():
    master = cargar_master()
    ignoradas = cargar_ignoradas()
    keywords_vistas = recolectar_keywords_vistas()
    sin_mapear = encontrar_sin_mapear(keywords_vistas, master, ignoradas)

    if not sin_mapear:
        print("No hay keywords pendientes de mapear por ahora. Tu keyword_tag_map está al día")
        print("(o todavía no has generado ninguna vacante con el parser corrido).")
        return

    tags_conocidos = sorted(recolectar_tags_conocidos(master))
    print(f"Encontré {len(sin_mapear)} keyword(s) sin mapear en tus vacantes capturadas.\n")

    nuevos_mapeos: dict[str, str] = {}

    for i, kw in enumerate(sin_mapear, start=1):
        opciones = tags_conocidos + ["Ignorar esta keyword (no volver a preguntar)", "Escribir un tag nuevo a mano"]
        seleccion = elegir_opcion(f"[{i}/{len(sin_mapear)}] ¿Qué tag le corresponde a \"{kw}\"?", opciones)

        if seleccion == len(opciones) - 1:
            guardar_ignorada(kw)
            print(f"  -> ignorada, no se volverá a preguntar.")
        elif seleccion == len(opciones):
            nuevo_tag = input("  Escribe el tag nuevo (snake_case, ej. 'kanban'): ").strip()
            if nuevo_tag:
                nuevos_mapeos[kw] = nuevo_tag
        else:
            nuevos_mapeos[kw] = tags_conocidos[seleccion - 1]

    if not nuevos_mapeos:
        print("\nNo se agregó ningún mapeo nuevo esta vez.")
        return

    lineas = [f'  "{kw}": [{tag}]' for kw, tag in nuevos_mapeos.items()]
    bloque = "\n".join(lineas)

    SUGERENCIAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUGERENCIAS_PATH.write_text(bloque + "\n", encoding="utf-8")

    print(f"\n{'=' * 50}")
    print("Copia estas líneas dentro de tu bloque keyword_tag_map en perfil.yaml:")
    print(f"{'=' * 50}")
    print(bloque)
    print(f"{'=' * 50}")
    print(f"\n(este mismo bloque quedó guardado en: {SUGERENCIAS_PATH}, por si prefieres copiarlo desde ahí)")


if __name__ == "__main__":
    main()
