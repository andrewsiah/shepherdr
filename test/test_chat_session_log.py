"""Session bindings must remain exact when a shared daemon owns all rollout files."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("session_log", Path(__file__).resolve().parents[1] / "mods/chat/session-log.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SID = "01234567-1234-1234-1234-0123456789ab"
OTHER = "01234567-1234-1234-1234-0123456789ac"


class SessionLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.log = self.directory / "rollout.jsonl"
        self.log.write_text(json.dumps({"type": "session_meta", "payload": {"id": SID}}) + "\n")
        self.payload = {"session_id": SID, "transcript_path": str(self.log)}
        self.info = {"state": "live", "foreground": {"name": "codex", "pid": 123}}
        for target, value in [("terminal_info", self.info), ("process_start", "start-one")]:
            p = patch.object(module, target, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.dict(os.environ, {}, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def bind(self):
        return module.capture(self.payload, "t1", self.directory)

    def test_daemon_binding_resolves_without_a_rollout_file_descriptor(self):
        self.assertTrue(self.bind())
        self.assertEqual(module.find(123, self.directory), str(self.log))
        self.assertEqual((self.directory / "codex-123.json").stat().st_mode & 0o777, 0o600)

    def test_pid_reuse_does_not_reopen_old_session(self):
        self.bind()
        module.process_start.return_value = "start-two"
        self.assertIsNone(module.find(123, self.directory))

    def test_changed_foreground_does_not_reopen_old_session(self):
        self.bind()
        self.info["foreground"]["pid"] = 124
        self.assertIsNone(module.find(123, self.directory))

    def test_transcript_identity_must_match(self):
        self.payload["session_id"] = OTHER
        self.assertFalse(self.bind())
        self.assertFalse((self.directory / "codex-123.json").exists())

    def test_transcript_replacement_is_rejected(self):
        self.bind()
        self.log.write_text(json.dumps({"type": "session_meta", "payload": {"id": OTHER}}) + "\n")
        self.assertIsNone(module.find(123, self.directory))

    def test_child_session_cannot_claim_parent_terminal(self):
        os.environ["CODEX_THREAD_ID"] = OTHER
        self.assertFalse(self.bind())

    def test_new_session_replaces_binding_for_same_live_client(self):
        self.bind()
        self.log.write_text(json.dumps({"type": "session_meta", "payload": {"id": OTHER}}) + "\n")
        self.payload["session_id"] = OTHER
        self.assertTrue(self.bind())
        self.assertEqual(json.loads((self.directory / "codex-123.json").read_text())["session_id"], OTHER)

    def test_session_start_can_precede_first_transcript_write(self):
        self.log.unlink()
        self.assertTrue(self.bind())
        self.assertEqual(module.find(123, self.directory), "pending")
        self.log.write_text(json.dumps({"type": "session_meta", "payload": {"id": SID}}) + "\n")
        self.assertEqual(module.find(123, self.directory), str(self.log))
