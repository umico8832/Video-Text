from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from advanced_model_utils import model_action_status, run_info_status, status_label_style
from model_config import LOCAL_MODEL_VALUE


class AdvancedModelUtilsTest(unittest.TestCase):
    def create_valid_model(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        for name in ("config.json", "model.bin", "tokenizer.json"):
            (directory / name).write_text("test", encoding="utf-8")

    def test_model_action_status_for_preset(self):
        self.assertEqual(model_action_status("small", "", {"small"}), "已部署，可离线使用。")
        self.assertEqual(model_action_status("tiny", "", {"small"}), "未部署，可点击下载/部署。")
        self.assertEqual(model_action_status("", "", set()), "请选择 Whisper 模型。")

    def test_model_action_status_for_local_model(self):
        with TemporaryDirectory() as directory:
            valid_model = Path(directory) / "valid"
            self.create_valid_model(valid_model)
            missing_files = Path(directory) / "missing-files"
            missing_files.mkdir()

            self.assertEqual(model_action_status(LOCAL_MODEL_VALUE, "", set()), "请选择本地模型目录。")
            self.assertEqual(model_action_status(LOCAL_MODEL_VALUE, str(valid_model), set()), "本地模型目录可用。")
            self.assertEqual(
                model_action_status(LOCAL_MODEL_VALUE, str(missing_files), set()),
                "本地模型目录缺少基本模型文件。",
            )
            self.assertEqual(
                model_action_status(LOCAL_MODEL_VALUE, str(Path(directory) / "missing"), set()),
                "本地模型目录不存在。",
            )

    def test_status_label_style_uses_known_and_unknown_colors(self):
        self.assertIn("#166534", status_label_style("ok"))
        self.assertIn("#334155", status_label_style("not-a-state"))

    def test_run_info_status(self):
        self.assertEqual(
            run_info_status({"whisper": {"ok": True, "version": "1.2.3"}, "cuda": {"ok": False}}),
            (
                ("语音识别：可用", "ok"),
                ("GPU 加速：不可用", "bad"),
                ("faster-whisper 版本：1.2.3", "unknown"),
            ),
        )
        self.assertEqual(
            run_info_status(None),
            (
                ("语音识别：未检测", "unknown"),
                ("GPU 加速：未检测", "unknown"),
                ("faster-whisper 版本：未知", "unknown"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
