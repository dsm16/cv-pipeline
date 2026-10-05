"""
intake_common.py — funciones compartidas entre cualquier forma de capturar
una vacante (manual hoy, scraper más adelante). Todas terminan escribiendo
el mismo formato de archivo (raw.txt con metadata + '---' + descripción),
así el resto del pipeline (parser.py) nunca necesita saber de dónde vino
la vacante.
"""

import re
import unicodedata
from pathlib import Path

# Subcarpeta donde vive todo lo "de trabajo" del pipeline (raw.txt,
# parsed.json, seleccion.yaml, HTML intermedio) — así la carpeta principal
# de la vacante solo muestra lo que de verdad importa: el/los PDF finales
# y el acceso directo a la vacante original.
PIPELINE_SUBDIR = "_pipeline"


def carpeta_cv_full(base: Path, nombre: str) -> Path:
    """Accept a single portable folder name, never an absolute/parent path."""
    nombre = nombre.strip()
    reservados = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)
    }
    if (
        not nombre or nombre in {".", ".."}
        or re.search(r'[<>:"/\\|?*\x00-\x1f]', nombre)
        or nombre.endswith((".", " "))
        or nombre.split(".", 1)[0].upper() in reservados
    ):
        raise ValueError("Usa un nombre de carpeta simple, sin rutas ni caracteres reservados.")
    carpeta = base / nombre
    if not carpeta.resolve().is_relative_to(base.resolve()):
        raise ValueError("La carpeta debe permanecer dentro del directorio de vacantes.")
    return carpeta


def ruta_pipeline(carpeta: Path) -> Path:
    ruta = carpeta / PIPELINE_SUBDIR
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _slug(texto: str) -> str:
    """
    Convierte texto libre en algo válido para nombre de carpeta:
    minúsculas, sin acentos, espacios -> guion bajo, sin símbolos raros.
    'Google México!' -> 'google_mexico'
    """
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    return texto.strip("_")


def _acortar(slug: str, max_len: int) -> str:
    """
    Corta un slug a un largo máximo, sin dejarlo a la mitad de una palabra.
    'analista_de_business_intelligence' con max_len=20 -> 'analista_de_business'
    """
    if len(slug) <= max_len:
        return slug
    recortado = slug[:max_len]
    if "_" in recortado:
        recortado = recortado.rsplit("_", 1)[0]
    return recortado


def generar_nombre_carpeta(empresa: str, titulo: str) -> str:
    empresa_slug = _acortar(_slug(empresa), 20)
    titulo_slug = _acortar(_slug(titulo), 30)
    return f"{empresa_slug}__{titulo_slug}"


def crear_acceso_directo(carpeta: Path, url: str) -> None:
    """
    Crea un archivo .url (acceso directo de Windows) para abrir la vacante
    original con doble clic, directo desde el explorador de archivos.
    """
    if not url:
        return
    contenido = f"[InternetShortcut]\nURL={url}\n"
    (carpeta / "abrir_vacante.url").write_text(contenido, encoding="utf-8")


def guardar_vacante(carpeta: Path, metadata: dict, descripcion: str) -> Path:
    """
    Crea la carpeta (agregando _2, _3... si el nombre ya existe, para
    nunca sobrescribir una vacante guardada antes) y escribe raw.txt
    en el formato exacto que parser.py espera.
    """
    carpeta_final = carpeta
    contador = 2
    while carpeta_final.exists():
        carpeta_final = carpeta.parent / f"{carpeta.name}_{contador}"
        contador += 1

    carpeta_final.mkdir(parents=True)

    encabezado = "\n".join(f"{clave.upper()}: {valor}" for clave, valor in metadata.items())
    contenido = f"{encabezado}\n---\n{descripcion}\n"

    (ruta_pipeline(carpeta_final) / "raw.txt").write_text(contenido, encoding="utf-8")
    crear_acceso_directo(carpeta_final, metadata.get("url", ""))
    return carpeta_final
