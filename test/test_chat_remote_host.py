"""Remote exec's minimal PATH must still reach the installed core client."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("remote_session_log", Path(__file__).resolve().parents[1] / "mods/chat/session-log.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RemoteHost(unittest.TestCase):
    def test_core_client_outside_noninteractive_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            hc = home / ".local/bin/hc"
            hc.parent.mkdir(parents=True)
            info = {"state": "live", "foreground": {"name": "codex", "pid": 123}}
            hc.write_text("#!/bin/sh\nprintf '%s\\n' '" + json.dumps(info) + "'\n")
            hc.chmod(0o700)
            with patch.object(module.shutil, "which", return_value=None), patch.object(module.Path, "home", return_value=home):
                self.assertEqual(module.terminal_info("t1"), info)
