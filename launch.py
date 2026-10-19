"""Opens the which-key popup. Popups do not get HERDR_PANE_ID, so the
focused ids are forwarded explicitly (the popup also reads
HERDR_PLUGIN_CONTEXT_JSON as a fallback).

Popup size comes from width/height on the [[panes]] entry in
herdr-plugin.toml; `plugin pane open` has no size flags.
"""
import os
import subprocess
import sys

env = os.environ.get
sys.exit(subprocess.call([
    env("HERDR_BIN_PATH") or "herdr", "plugin", "pane", "open",
    "--plugin", env("HERDR_PLUGIN_ID", ""), "--entrypoint", "menu",
    "--env", "WK_WORKSPACE=" + env("HERDR_WORKSPACE_ID", ""),
    "--env", "WK_TAB=" + env("HERDR_TAB_ID", ""),
    "--env", "WK_PANE=" + env("HERDR_PANE_ID", ""),
]))
