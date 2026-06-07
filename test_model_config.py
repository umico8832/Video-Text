from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from model_config import (
    LOCAL_MODEL_VALUE,
    get_model_choices,
    get_model_settings_fields,
    is_valid_model_dir,
    resolve_model_from_settings,
    resolve_preset_model_for_extract,
    scan_deployed_models,
)
from workers import ModelDeployWorker


class ModelConfigTest(unittest.TestCase):
    def create_valid_model(self, directory: Path):
        directory.mkdir(parents=True)
        for name in ("config.json", "model.bin", "tokenizer.json"):
            (directory / name).write_text("test", encoding="utf-8")

    def test_preset_settings(self):
        self.assertEqual(
            get_model_settings_fields("small"),
            {"model_source": "preset", "model": "small"},
        )

    def test_local_settings(self):
        self.assertEqual(
            get_model_settings_fields(LOCAL_MODEL_VALUE, "D:/models/whisper"),
            {"model_source": "local", "model": "D:/models/whisper"},
        )

    def test_unknown_legacy_model_becomes_local(self):
        selection = resolve_model_from_settings({"model": "legacy-unknown-model"})
        self.assertEqual(selection.selected_value, LOCAL_MODEL_VALUE)
        self.assertEqual(selection.local_value, "legacy-unknown-model")

    def test_legacy_custom_source_becomes_local(self):
        selection = resolve_model_from_settings(
            {"model_source": "custom", "model": "D:/old-model"}
        )
        self.assertEqual(selection.selected_value, LOCAL_MODEL_VALUE)
        self.assertEqual(selection.local_value, "D:/old-model")

    def test_scan_and_format_deployed_model(self):
        with TemporaryDirectory() as directory:
            models_dir = Path(directory)
            self.create_valid_model(models_dir / "small")
            self.assertEqual(scan_deployed_models(models_dir), {"small"})
            labels = dict((value, label) for label, value in get_model_choices({"small"}))
            self.assertEqual(labels["small"], "small  ✅ 可用")
            self.assertEqual(labels["tiny"], "tiny")

    def test_empty_model_directory_is_not_valid(self):
        with TemporaryDirectory() as directory:
            model_dir = Path(directory) / "small"
            model_dir.mkdir()
            self.assertFalse(is_valid_model_dir(model_dir))

    def test_extract_prefers_valid_project_model(self):
        with TemporaryDirectory() as directory:
            models_dir = Path(directory)
            model_dir = models_dir / "small"
            self.create_valid_model(model_dir)
            self.assertEqual(
                resolve_preset_model_for_extract("small", models_dir),
                str(model_dir),
            )
            self.assertEqual(
                resolve_preset_model_for_extract("tiny", models_dir),
                "tiny",
            )


class ModelDeployWorkerTest(unittest.TestCase):
    def create_valid_model(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        for name in ("config.json", "model.bin", "tokenizer.json"):
            (directory / name).write_text("test", encoding="utf-8")

    def run_worker(self, source, model, models_dir=None):
        results = []
        worker = ModelDeployWorker(source, model, models_dir)
        worker.done.connect(lambda ok, message: results.append((ok, message)))
        worker.run()
        return results

    @patch("faster_whisper.utils.download_model")
    def test_existing_local_directory_does_not_download(self, download_model):
        with TemporaryDirectory() as directory:
            self.create_valid_model(Path(directory))
            self.assertEqual(
                self.run_worker("local", directory),
                [(True, "本地模型目录可用")],
            )
        download_model.assert_not_called()

    @patch("faster_whisper.utils.download_model")
    def test_missing_local_directory_does_not_download(self, download_model):
        missing = str(Path("missing-local-model-directory").resolve())
        self.assertEqual(
            self.run_worker("local", missing),
            [(False, "本地模型目录不存在")],
        )
        download_model.assert_not_called()

    @patch("workers.get_official_model_dir")
    @patch("faster_whisper.utils.download_model")
    def test_preset_download_uses_project_model_directory(
        self,
        download_model,
        official_model_dir,
    ):
        with TemporaryDirectory() as directory:
            model_dir = Path(directory) / "small"
            official_model_dir.return_value = model_dir
            download_model.side_effect = lambda *args, **kwargs: self.create_valid_model(
                Path(kwargs["output_dir"])
            )
            self.assertEqual(
                self.run_worker("preset", "small"),
                [(True, "已部署")],
            )
            download_model.assert_called_once_with("small", output_dir=str(model_dir))

    @patch("faster_whisper.utils.download_model")
    def test_preset_download_uses_custom_model_directory(self, download_model):
        with TemporaryDirectory() as directory:
            model_dir = Path(directory) / "small"
            download_model.side_effect = lambda *args, **kwargs: self.create_valid_model(
                Path(kwargs["output_dir"])
            )
            self.assertEqual(
                self.run_worker("preset", "small", directory),
                [(True, "已部署")],
            )
            download_model.assert_called_once_with("small", output_dir=str(model_dir))


if __name__ == "__main__":
    unittest.main()
