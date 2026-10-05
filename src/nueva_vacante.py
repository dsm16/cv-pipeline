"""
nueva_vacante.py — punto de entrada interactivo del pipeline.

Hoy solo existe el modo manual (tú pegas el texto). Cuando el scraper
(Fase 1) esté listo, se conecta aquí como una segunda opción, reusando
intake_common.py — el resto del pipeline no cambia en absoluto.

Uso:
    python src/nueva_vacante.py
"""

import sys
from pathlib import Path

from intake_common import generar_nombre_carpeta, guardar_vacante

RAIZ = Path(__file__).parent.parent
VACANTES_DIR = RAIZ / "vacantes"


def capturar_manual() -> tuple[dict, str]:
    print("\n--- Nueva vacante (modo manual) ---\n")

    titulo = input("Título del puesto tal como aparece en la vacante (ej. 'Analista de Datos Senior'): ").strip()
    empresa = input("Nombre de la empresa que publica la vacante (ej. 'Google México'): ").strip()
    ubicacion = input("Ciudad o ubicación de la vacante (ej. 'CDMX'): ").strip()
    modalidad = input("Modalidad de trabajo — escribe remoto, híbrido o presencial: ").strip()
    url = input("URL de la vacante (opcional — pégala para poder reabrirla después, Enter para omitir): ").strip()

    print("\nAhora pega el texto COMPLETO de la descripción de la vacante")
    print("(copiado tal cual del sitio donde la viste).")
    print("Cuando termines de pegarlo, escribe la palabra FIN en una línea")
    print("nueva (sola, sin nada más) y presiona Enter para continuar:\n")
    lineas = []
    while True:
        linea = input()
        if linea.strip().upper() == "FIN":
            break
        lineas.append(linea)
    descripcion = "\n".join(lineas).strip()

    metadata = {
        "titulo": titulo,
        "empresa": empresa,
        "ubicacion": ubicacion,
        "modalidad": modalidad,
        "url": url,
    }
    return metadata, descripcion


def main():
    print("¿Cómo quieres capturar la vacante?")
    print("  1) Manual        — tú pegas el texto de la vacante que copiaste")
    print("  2) Scraper automático — el programa la busca solo (aún no disponible en esta versión)")
    opcion = input("Escribe 1 o 2 y presiona Enter [Enter = 1]: ").strip() or "1"

    if opcion == "2":
        print("\nEl scraper todavía no está implementado en esta versión del pipeline.")
        print("Vuelve a correr el programa y elige la opción 1 (manual) por ahora.")
        sys.exit(0)

    metadata, descripcion = capturar_manual()

    nombre_carpeta = generar_nombre_carpeta(metadata["empresa"], metadata["titulo"])
    carpeta = guardar_vacante(VACANTES_DIR / nombre_carpeta, metadata, descripcion)

    print(f"\nListo. Se creó la carpeta: {carpeta}")
    print(f"Dentro quedó guardado el archivo raw.txt con todo lo que capturaste.")

    correr_parser = input(
        "\n¿Quieres correr el parser ahora mismo para detectar las keywords "
        "que coinciden con tu perfil? Escribe s para sí, o n para no: "
    ).strip().lower()
    if correr_parser == "s":
        import vacante_parser
        vacante_parser.main(str(carpeta), "python")

        correr_matcher = input(
            "\n¿Quieres generar la selección automática de resumen y bullets "
            "ahora mismo (seleccion.yaml)? Escribe s para sí, o n para no: "
        ).strip().lower()
        if correr_matcher == "s":
            import matcher
            matcher.main(str(carpeta), 3, 2)


if __name__ == "__main__":
    main()