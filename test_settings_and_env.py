from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import settings_manager
from env_checker import format_command_for_log


class SettingsManagerTest(unittest.TestCase):
    def test_save_settings_replaces_file_with_valid_json(self):
        with TemporaryDirectory() as directory:
            settings_file = Path(directory) / "settings.json"
            with patch.object(settings_manager, "SETTINGS_FILE", settings_file):
                settings_manager.save_settings({"url": "https://example.test", "model": "small"})

            self.assertEqual(
                settings_file.read_text(encoding="utf-8"),
                '{\n  "url": "https://example.test",\n  "model": "small"\n}\n',
            )
            self.assertFalse(list(Path(directory).glob("tmp*")))

    def test_load_settings_falls_back_to_defaults_for_invalid_json(self):
        with TemporaryDirectory() as directory:
            settings_file = Path(directory) / "settings.json"
            settings_file.write_text("{invalid", encoding="utf-8")
            with patch.object(settings_manager, "SETTINGS_FILE", settings_file):
                settings = settings_manager.load_settings()

            self.assertEqual(settings["device"], "auto")
            self.assertEqual(settings["cookie_mode"], "none")


class EnvCheckerTest(unittest.TestCase):
    def test_format_command_for_log_quotes_spaces(self):
        command = format_command_for_log(["python", "-m", "pip", "install", "some package"])

        self.assertEqual(command, "python -m pip install 'some package'")

    def test_format_command_for_log_masks_sensitive_values(self):
        command = format_command_for_log(
            ["tool", "--token", "abc123", "--password=secret", "--name", "visible"]
        )

        self.assertEqual(command, "tool --token '***' '--password=***' --name visible")


if __name__ == "__main__":
    unittest.main()
