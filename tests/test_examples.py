"""Exercise synthetic data and profile routing without private data or PDFs."""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml
import config
import matcher
import render
import vacante_parser

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/perfil.example.yaml"


class SyntheticWorkflowTests(unittest.TestCase):
    def test_profile_precedence_preserves_private_data(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CV_PIPELINE_PROFILE": ""}):
            root = Path(directory)
            self.assertEqual(config.resolver_perfil(root), root / "examples/perfil.example.yaml")
            private = root / "master/perfil.yaml"
            private.parent.mkdir()
            private.write_text("synthetic test marker", encoding="utf-8")
            self.assertEqual(config.resolver_perfil(root), private)
            with patch.dict(os.environ, {"CV_PIPELINE_PROFILE": "examples/perfil.example.yaml"}):
                self.assertEqual(config.resolver_perfil(root), root / "examples/perfil.example.yaml")
            self.assertEqual(private.read_text(encoding="utf-8"), "synthetic test marker")

    def test_synthetic_vacancy_to_bilingual_html(self):
        master = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory, patch.object(vacante_parser, "MASTER_PATH", EXAMPLE), patch.object(matcher, "MASTER_PATH", EXAMPLE), contextlib.redirect_stdout(io.StringIO()):
            folder = Path(directory)
            pipeline = folder / "_pipeline"
            pipeline.mkdir()
            (pipeline / "raw.txt").write_text((ROOT / "examples/vacante.example.txt").read_text(encoding="utf-8"), encoding="utf-8")
            vacante_parser.main(str(folder), "python")
            parsed = json.loads((pipeline / "parsed.json").read_text(encoding="utf-8"))
            self.assertEqual(parsed["keywords_detectadas"], ["Automation", "CSV", "Python", "SQL", "Validation"])
            matcher.main(str(folder), 1, 1)
            selection = yaml.safe_load((pipeline / "seleccion.yaml").read_text(encoding="utf-8"))
            self.assertEqual(selection["resumen_id"], "automation")
            self.assertEqual(selection["bullets_seleccionados"], ["archive_import"])
            for language in ["es", "en"]:
                html = render.renderizar_html(selection, master, language)
                self.assertIn(f'<html lang="{language}">', html)
                self.assertIn("mira@example.invalid", html)

    def test_full_mode_still_includes_all_content_with_zero_limits(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(matcher, "MASTER_PATH", EXAMPLE), contextlib.redirect_stdout(io.StringIO()):
            matcher.main(directory, 0, 0, full=True)
            selection = yaml.safe_load((Path(directory) / "_pipeline/seleccion.yaml").read_text(encoding="utf-8"))
            self.assertEqual(len(selection["bullets_seleccionados"]), 2)
            self.assertEqual(len(selection["proyectos_seleccionados"]), 2)
