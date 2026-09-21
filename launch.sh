#!/bin/sh
# Opens the which-key popup. Popups do not get HERDR_PANE_ID, so the
# focused ids are forwarded explicitly (the popup also reads
# HERDR_PLUGIN_CONTEXT_JSON as a fallback).
#
# Popup size comes from width/height on the [[panes]] entry in
# herdr-plugin.toml; `plugin pane open` has no size flags.
exec "${HERDR_BIN_PATH:-herdr}" plugin pane open \
  --plugin "$HERDR_PLUGIN_ID" --entrypoint menu \
  --env "WK_WORKSPACE=${HERDR_WORKSPACE_ID:-}" \
  --env "WK_TAB=${HERDR_TAB_ID:-}" \
  --env "WK_PANE=${HERDR_PANE_ID:-}"
