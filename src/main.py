"""
main.py — punto de entrada único del pipeline.

Todo lo demás (captura de vacante, parser, matcher, render) se orquesta
desde aquí con menús numerados. Los scripts individuales (nueva_vacante.py,
vacante_parser.py, matcher.py, render.py) se pueden seguir usando sueltos
para pruebas o depuración, pero el uso normal del día a día es este.

Uso:
    python src/main.py
"""

from pathlib import Path

import matcher
import qa
import render
import vacante_parser
from cli_utils import elegir_opcion, elegir_idioma
from intake_common import generar_nombre_carpeta, guardar_vacante, carpeta_cv_full
from nueva_vacante import capturar_manual

RAIZ = Path(__file__).parent.parent
VACANTES_DIR = RAIZ / "vacantes"


def flujo_vacante_manual():
    """
    Captura una o varias vacantes en fila (te pregunta después de cada
    una si quieres capturar otra), y hasta el final —una sola vez—
    corre parser + matcher + render para todas las que hayas capturado.
    Así no repites las mismas preguntas de idioma/proceso por cada vacante.
    """
    carpetas = []

    while True:
        metadata, descripcion = capturar_manual()
        nombre_carpeta = generar_nombre_carpeta(metadata["empresa"], metadata["titulo"])
        carpeta = guardar_vacante(VACANTES_DIR / nombre_carpeta, metadata, descripcion)
        carpetas.append(carpeta)
        print(f"\nVacante guardada: {carpeta}")

        continuar = elegir_opcion(
            "¿Qué quieres hacer ahora?",
            ["Capturar otra vacante", f"Ya no, generar el/los CV ({len(carpetas)} vacante(s) capturada(s))"],
        )
        if continuar == 2:
            break

    lang = elegir_idioma()

    for i, carpeta in enumerate(carpetas, start=1):
        print(f"\n=== Procesando {i}/{len(carpetas)}: {carpeta.name} ===")
        vacante_parser.main(str(carpeta), "python")
        matcher.main(str(carpeta), 3, 2)
        render.main(str(carpeta), lang)
        qa.main(str(carpeta))

    print(f"\nListo. Se generaron {len(carpetas)} CV(s):")
    for carpeta in carpetas:
        print(f"  {carpeta}")


def flujo_cv_full():
    while True:
        nombre_carpeta = input("\nNombre para esta carpeta (Enter para usar 'cv_full'): ").strip() or "cv_full"
        try:
            carpeta = carpeta_cv_full(VACANTES_DIR, nombre_carpeta)
            break
        except ValueError as error:
            print(f"[aviso] {error}")

    print("\n--- Armando tu CV completo (sin filtrar por vacante) ---")
    matcher.main(str(carpeta), 0, 0, full=True)

    lang = elegir_idioma()
    print("\n--- Generando PDF ---")
    render.main(str(carpeta), lang)
    qa.main(str(carpeta))
    print(f"\nListo. Tu CV completo está en: {carpeta}")


def main():
    print("=" * 40)
    print("  CV PIPELINE")
    print("=" * 40)

    while True:
        opcion = elegir_opcion(
            "¿Qué quieres hacer?",
            [
                "Crear CV(s) para una o varias vacantes (captura manual)",
                "Crear CV completo con todo tu perfil (CV Full)",
                "Salir",
            ],
        )

        if opcion == 1:
            flujo_vacante_manual()
        elif opcion == 2:
            flujo_cv_full()
        elif opcion == 3:
            print("\nHasta luego.")
            break

        if opcion != 3:
            continuar = elegir_opcion("¿Quieres hacer algo más?", ["Sí, volver al menú", "No, salir"])
            if continuar == 2:
                print("\nHasta luego.")
                break


if __name__ == "__main__":
    main()
