"""Validate references and safe HTML without launching Chromium."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jinja2 import UndefinedError
import yaml
import matcher
import render

ROOT = Path(__file__).resolve().parents[1]


class RenderingRegressionTests(unittest.TestCase):
    def setUp(self):
        self.master = yaml.safe_load((ROOT / "examples/perfil.example.yaml").read_text(encoding="utf-8"))
        self.selection = {"resumen_id": "automation", "bullets_seleccionados": ["archive_import"], "proyectos_seleccionados": ["Validador de catálogo ficticio"]}

    def test_unknown_or_malformed_selections_fail_before_writing(self):
        bad = [None, {}, {**self.selection, "resumen_id": "missing"}, {**self.selection, "bullets_seleccionados": ["missing"]}, {**self.selection, "proyectos_seleccionados": ["missing"]}, {**self.selection, "bullets_seleccionados": "archive_import"}, {**self.selection, "bullets_seleccionados": [None]}]
        with tempfile.TemporaryDirectory() as directory, patch.object(render, "sync_playwright") as browser:
            target = Path(directory) / "must_not_exist"
            for selection in bad:
                with self.subTest(selection=selection), self.assertRaises(ValueError):
                    render.renderizar_idioma(target, selection, self.master, "es")
                self.assertFalse(target.exists())
            browser.assert_not_called()

    def test_invalid_full_summary_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(matcher, "MASTER_PATH", ROOT / "examples/perfil.example.yaml"):
            target = Path(directory) / "must_not_exist"
            with self.assertRaises(ValueError):
                matcher.main(str(target), 0, 0, full=True, resumen_override="missing")
            self.assertFalse(target.exists())

    def test_html_is_escaped_and_undefined_template_fields_raise(self):
        self.master["datos_personales"]["nombre"] = '<script>alert("sample")</script>'
        html = render.renderizar_html(self.selection, self.master, "es")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        with self.assertRaises(UndefinedError):
            render.crear_entorno().from_string("{{ absent }}").render()

    def test_missing_required_content_fails_but_translation_fallback_survives(self):
        fallback = copy.deepcopy(self.master)
        del fallback["resumenes"][0]["texto_en"]
        html = render.renderizar_html(self.selection, fallback, "en")
        self.assertIn(fallback["resumenes"][0]["texto"], html)
        del fallback["resumenes"][0]["texto"]
        with self.assertRaises(ValueError):
            render.renderizar_html(self.selection, fallback, "en")

    def test_optional_metric_and_project_selection_remain_optional(self):
        del self.master["experiencia"][0]["bullets"][0]["metrica"]
        selection = {"resumen_id": "automation", "bullets_seleccionados": ["archive_import"]}
        self.assertIn("Construí un importador", render.renderizar_html(selection, self.master, "es"))
