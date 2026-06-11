from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_config import LOCAL_MODEL_VALUE
from gui_model_utils import device_display_text, model_summary_text, selected_model_status


class GuiModelUtilsTest(unittest.TestCase):
    def create_valid_model(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        for name in ("config.json", "model.bin", "tokenizer.json"):
            (directory / name).write_text("test", encoding="utf-8")

    def test_model_summary_text_for_preset_models(self):
        self.assertEqual(model_summary_text("small", "", {"small"}), "small（已部署）")
        self.assertEqual(model_summary_text("tiny", "", {"small"}), "tiny（未部署）")
        self.assertEqual(model_summary_text("", "", set()), "未选择识别模型")

    def test_model_summary_text_for_local_model(self):
        self.assertEqual(model_summary_text(LOCAL_MODEL_VALUE, "D:/models/local", set()), "本地模型")
        self.assertEqual(model_summary_text(LOCAL_MODEL_VALUE, "", set()), "本地模型未选择")

    def test_device_display_text(self):
        self.assertEqual(device_display_text("cpu"), "CPU 模式")
        self.assertEqual(device_display_text("cuda"), "GPU 模式")
        self.assertEqual(device_display_text("auto"), "自动选择")
        self.assertEqual(device_display_text("custom"), "custom")

    def test_selected_model_status_for_local_model(self):
        with TemporaryDirectory() as directory:
            model_dir = Path(directory) / "local"
            self.create_valid_model(model_dir)
            missing_files_dir = Path(directory) / "missing-files"
            missing_files_dir.mkdir()

            self.assertEqual(
                selected_model_status(LOCAL_MODEL_VALUE, str(model_dir), set()),
                "本地模型目录可用",
            )
            self.assertEqual(
                selected_model_status(LOCAL_MODEL_VALUE, str(missing_files_dir), set()),
                "本地模型目录缺少基本模型文件",
            )
            self.assertEqual(
                selected_model_status(LOCAL_MODEL_VALUE, str(Path(directory) / "missing"), set()),
                "本地模型目录不存在",
            )
            self.assertEqual(selected_model_status(LOCAL_MODEL_VALUE, "", set()), "未检查")

    def test_selected_model_status_for_preset_model(self):
        self.assertEqual(selected_model_status("small", "", {"small"}), "已部署")
        self.assertEqual(selected_model_status("tiny", "", {"small"}), "未部署")


if __name__ == "__main__":
    unittest.main()
