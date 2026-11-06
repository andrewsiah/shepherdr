#!/usr/bin/env python3
"""Exact Codex SessionStart bindings for clients whose daemon owns the rollout."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def process_start(pid):
    return subprocess.check_output(["ps", "-p", str(pid), "-o", "lstart="],
                                   text=True, timeout=2).strip()


def terminal_info(terminal):
    return json.loads(subprocess.check_output(["hc", "get", terminal, "--json"],
                                             text=True, timeout=2))


def transcript_id(path):
    with Path(path).open(encoding="utf-8") as f:
        row = json.loads(f.readline(1048576))
    if row.get("type") != "session_meta":
        return None
    return row.get("payload", {}).get("id") or row.get("payload", {}).get("session_id")


def capture(payload, terminal, directory):
    if payload.get("hook_event_name") not in (None, "SessionStart"):
        return False
    sid = payload.get("session_id")
    path = payload.get("transcript_path")
    if not isinstance(sid, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", sid):
        return False
    if not isinstance(path, str) or not Path(path).is_absolute():
        return False
    if Path(path).exists() and transcript_id(path) != sid:
        return False
    # A child agent must never claim the terminal inherited from its parent.
    inherited = os.environ.get("CODEX_THREAD_ID")
    if inherited and inherited != sid:
        return False
    info = terminal_info(terminal)
    fg = info.get("foreground") or {}
    if info.get("state") != "live" or fg.get("name") != "codex":
        return False
    pid = fg.get("pid")
    start = process_start(pid)
    if not start:
        return False
    record = dict(kind="codex", terminal=terminal, pid=pid, start=start, session_id=sid, path=path)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".session-", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(record, f)
        os.replace(tmp, directory / f"codex-{pid}.json")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True


def find(pid, directory):
    record = json.loads((directory / f"codex-{pid}.json").read_text())
    if record.get("kind") != "codex" or record.get("pid") != pid:
        return None
    if not record.get("start") or process_start(pid) != record["start"]:
        return None
    info = terminal_info(record["terminal"])
    fg = info.get("foreground") or {}
    if info.get("state") != "live" or fg.get("name") != "codex" or fg.get("pid") != pid:
        return None
    if not Path(record["path"]).exists():
        return "pending"
    if transcript_id(record["path"]) != record.get("session_id"):
        return None
    return record["path"]


def main():
    app = Path(os.environ.get("HERDR_APP_HOME", str(Path.home() / ".config/herdr-app")))
    directory = app / "data/chat-sessions"
    try:
        if sys.argv[1] == "capture":
            terminal = os.environ.get("HC_TERMINAL_ID")
            if terminal:
                capture(json.load(sys.stdin), terminal, directory)
        elif sys.argv[1] == "find":
            path = find(int(sys.argv[2]), directory)
            if path:
                print(path)
    except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError):
        pass  # No exact identity: leave discovery empty, never pick another conversation.


if __name__ == "__main__":
    main()
