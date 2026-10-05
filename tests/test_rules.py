"""Regression checks for the audit's parsing, date, and matching bugs."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from extractor_python import extraer
from intake_common import carpeta_cv_full
from matcher import elegir_bullets, elegir_proyectos, elegir_resumen
from qa import calcular_cobertura
from utils import formatear_fecha
from vacante_parser import parsear_metadata


class RuleRegressionTests(unittest.TestCase):
    def test_keyword_boundaries_and_punctuation(self):
        result = extraer("Python, SQL; C++ and C#; MySQLite SQLAlchemy", ["Python", "SQL", "C++", "C#", "C"])
        self.assertEqual(result["keywords_detectadas"], ["C#", "C++", "Python", "SQL"])
        self.assertEqual(extraer("MySQLite SQLAlchemy XC++ C#tools", ["SQL", "C++", "C#"])["keywords_detectadas"], [])

    def test_qa_uses_the_same_keyword_boundaries(self):
        self.assertEqual(calcular_cobertura("MySQLite; C++, C#", ["SQL", "C++", "C#"]), (["C++", "C#"], ["SQL"]))

    def test_metadata_keeps_url_colons_and_rejects_missing_separator(self):
        metadata, text = parsear_metadata("URL: https://example.invalid/job\n---\nPython")
        self.assertEqual(metadata["url"], "https://example.invalid/job")
        self.assertEqual(text, "Python")
        with self.assertRaises(ValueError):
            parsear_metadata("TITULO: No separator")

    def test_invalid_months_raise_value_error(self):
        for date in ["2025-00", "2025-13", "2025-xx", "2025-1", "0000-01"]:
            with self.subTest(date=date), self.assertRaises(ValueError):
                formatear_fecha(date, "es")

    def test_supported_dates_and_translation_are_preserved(self):
        for value, lang, expected in [("2025-01", "es", "enero 2025"), ("2025-12", "en", "December 2025"), ("2025", "es", "2025"), ("presente", "en", "Present"), ("cursando", "es", "Cursando")]:
            with self.subTest(value=value, lang=lang):
                self.assertEqual(formatear_fecha(value, lang), expected)

    def test_limits_and_fallbacks(self):
        jobs = [{"empresa": "Fictional", "bullets": [{"id": "first", "tags": ["python"]}, {"id": "second", "tags": ["sql"]}]}]
        projects = [{"nombre": "first", "tags": ["python"]}, {"nombre": "second", "tags": ["sql"]}]
        for tags in [set(), {"python"}]:
            with self.subTest(tags=tags):
                self.assertEqual(elegir_bullets(jobs, tags, 0)[0], [])
                self.assertEqual(elegir_proyectos(projects, tags, 0), [])
                self.assertEqual(elegir_bullets(jobs, tags, 1)[0], ["first"])
                self.assertEqual(elegir_proyectos(projects, tags, 1), ["first"])
        with self.assertRaises(ValueError):
            elegir_bullets(jobs, set(), -1)
        with self.assertRaises(ValueError):
            elegir_proyectos(projects, set(), -1)

    def test_empty_summaries_fail_explicitly(self):
        with self.assertRaises(ValueError):
            elegir_resumen([], set())

    def test_full_cv_folder_must_stay_inside_output_directory(self):
        base = Path(__file__).resolve().parents[1] / "vacantes"
        self.assertEqual(carpeta_cv_full(base, "demo_full"), base / "demo_full")
        for name in ["", ".", "..", "../outside", "..\\outside", "/outside", "C:\\outside", "CON", "NUL.txt", "trailing."]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                carpeta_cv_full(base, name)
