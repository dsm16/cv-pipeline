"""
matcher.py — Fase 3 del pipeline.
Compara las keywords detectadas en la vacante (Fase 2) contra los tags de
tu master profile, y genera seleccion.yaml automáticamente — el mismo
archivo que antes escribías a mano.

Cómo traduce keywords -> tags:
  1. Intenta un match directo: convierte la keyword a slug y ve si
     coincide con algún tag que ya usas en el master profile.
  2. Si no coincide, busca en keyword_tag_map (dentro de perfil.yaml)
     un mapeo manual para esa keyword exacta.
  3. Si ninguna de las dos funciona, avisa en consola que esa keyword
     quedó sin traducir — es tu pista de qué agregar a keyword_tag_map.

Uso:
    python src/matcher.py vacantes/nombre_carpeta
    python src/matcher.py vacantes/nombre_carpeta --max-bullets 4
"""

import argparse
import json
from pathlib import Path

import yaml

from intake_common import _slug, ruta_pipeline
from config import MASTER_PATH
from utils import tags_overlap

RAIZ = Path(__file__).parent.parent


def cargar_yaml(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def recolectar_tags_conocidos(master: dict) -> set[str]:
    """Junta todos los tags que existen en cualquier parte del master profile."""
    conocidos = set()
    for r in master.get("resumenes", []):
        conocidos.update(r.get("tags", []))
    for exp in master.get("experiencia", []):
        for b in exp.get("bullets", []):
            conocidos.update(b.get("tags", []))
    for p in master.get("proyectos", []):
        conocidos.update(p.get("tags", []))
    return conocidos


def keywords_a_tags(keywords_detectadas: list[str], keyword_tag_map: dict, tags_conocidos: set[str]) -> set[str]:
    tags = set()
    no_mapeadas = []
    for kw in keywords_detectadas:
        candidatos = set(keyword_tag_map.get(kw, []))

        slug = _slug(kw)
        if slug in tags_conocidos:
            candidatos.add(slug)

        if candidatos:
            tags.update(candidatos)
        else:
            no_mapeadas.append(kw)

    if no_mapeadas:
        print(f"  [aviso] estas keywords no se pudieron traducir a ningún tag: {no_mapeadas}")
        print("  [aviso] agrégalas a 'keyword_tag_map' en perfil.yaml si quieres que cuenten en el matching.")

    return tags


def elegir_resumen(resumenes: list[dict], tags_vacante: set[str]) -> tuple[str, int]:
    if not resumenes:
        raise ValueError("El perfil debe contener al menos un resumen.")
    mejor_id, mejor_score = resumenes[0]["id"], -1
    for r in resumenes:
        score = len(tags_overlap(r["tags"], tags_vacante))
        if score > mejor_score:
            mejor_id, mejor_score = r["id"], score
    return mejor_id, mejor_score


def elegir_bullets(experiencia: list[dict], tags_vacante: set[str], max_por_experiencia: int):
    if max_por_experiencia < 0:
        raise ValueError("El máximo de bullets no puede ser negativo.")
    seleccionados = []
    detalle = []
    for exp in experiencia:
        puntuados = [(len(tags_overlap(b["tags"], tags_vacante)), b["id"]) for b in exp["bullets"]]
        puntuados.sort(key=lambda x: x[0], reverse=True)
        elegidos = [bid for score, bid in puntuados if score > 0][:max_por_experiencia]

        # Piso de seguridad: un trabajo nunca debe desaparecer del CV solo
        # porque ninguno de sus bullets coincidió con esta vacante en particular.
        # Mejor mostrar el logro más fuerte (el primero que definiste) que dejar un hueco.
        if max_por_experiencia > 0 and not elegidos and puntuados:
            elegidos = [puntuados[0][1]]
            print(f"  [aviso] {exp['empresa']}: sin match de tags, se incluyó el primer bullet por default")

        seleccionados.extend(elegidos)
        detalle.append((exp["empresa"], elegidos))
    return seleccionados, detalle


def elegir_proyectos(proyectos: list[dict], tags_vacante: set[str], max_proyectos: int):
    if max_proyectos < 0:
        raise ValueError("El máximo de proyectos no puede ser negativo.")
    puntuados = [(len(tags_overlap(p["tags"], tags_vacante)), p["nombre"]) for p in proyectos]
    puntuados.sort(key=lambda x: x[0], reverse=True)
    elegidos = [nombre for score, nombre in puntuados if score > 0][:max_proyectos]
    if max_proyectos > 0 and not elegidos and puntuados:
        elegidos = [puntuados[0][1]]
    return elegidos


def main(carpeta_vacante: str, max_bullets: int, max_proyectos: int, full: bool = False, resumen_override: str = None):
    if max_bullets < 0 or max_proyectos < 0:
        raise ValueError("Los límites no pueden ser negativos.")
    carpeta = Path(carpeta_vacante)
    master = cargar_yaml(MASTER_PATH)

    if not master.get("resumenes"):
        raise ValueError("El perfil debe contener al menos un resumen.")
    if full and resumen_override and resumen_override not in {r["id"] for r in master["resumenes"]}:
        raise ValueError(f"No encontré un resumen con id '{resumen_override}'")

    carpeta.mkdir(parents=True, exist_ok=True)

    if full:
        # Modo CV completo: sin filtrar por vacante, todo el master profile entra.
        resumen_id = resumen_override or master["resumenes"][0]["id"]
        bullets_seleccionados = [b["id"] for exp in master["experiencia"] for b in exp["bullets"]]
        proyectos_seleccionados = [p["nombre"] for p in master.get("proyectos", [])]
        print("Modo FULL: se incluyó todo el master profile, sin filtrar por ninguna vacante.")
    else:
        with open(ruta_pipeline(carpeta) / "parsed.json", encoding="utf-8") as f:
            parsed = json.load(f)

        tags_conocidos = recolectar_tags_conocidos(master)
        tags_vacante = keywords_a_tags(
            parsed.get("keywords_detectadas", []),
            master.get("keyword_tag_map", {}),
            tags_conocidos,
        )
        if not tags_vacante:
            print("  [aviso] no se tradujo ninguna keyword a tags — la selección será genérica.")

        resumen_id, score_resumen = elegir_resumen(master["resumenes"], tags_vacante)
        bullets_seleccionados, detalle = elegir_bullets(master["experiencia"], tags_vacante, max_bullets)
        proyectos_seleccionados = elegir_proyectos(master.get("proyectos", []), tags_vacante, max_proyectos)

        print(f"Resumen elegido: {resumen_id} (afinidad: {score_resumen} tags en común)")
        print("Bullets elegidos por experiencia:")
        for empresa, elegidos in detalle:
            print(f"  {empresa}: {elegidos if elegidos else '(ninguno con afinidad — revisa keyword_tag_map)'}")

    seleccion = {
        "resumen_id": resumen_id,
        "bullets_seleccionados": bullets_seleccionados,
        "proyectos_seleccionados": proyectos_seleccionados,
    }

    out_path = ruta_pipeline(carpeta) / "seleccion.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(seleccion, f, allow_unicode=True, sort_keys=False)

    print(f"\nseleccion.yaml generado: {out_path}")
    print(f"Proyectos incluidos: {proyectos_seleccionados}")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Genera seleccion.yaml automáticamente a partir de la vacante parseada.")
    cli.add_argument("carpeta_vacante", help="Carpeta de la vacante, ej: vacantes/prueba")
    cli.add_argument("--max-bullets", type=int, default=3, help="máximo de bullets por experiencia (default: 3)")
    cli.add_argument("--max-proyectos", type=int, default=2, help="máximo de proyectos a incluir (default: 2)")
    cli.add_argument("--full", action="store_true", help="Ignora el matching y arma seleccion.yaml con TODO el master profile (para un CV completo)")
    cli.add_argument("--resumen", default=None, help="id del resumen a usar en modo --full (default: el primero del master)")
    args = cli.parse_args()
    main(args.carpeta_vacante, args.max_bullets, args.max_proyectos, args.full, args.resumen)
