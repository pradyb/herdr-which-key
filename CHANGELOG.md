# Changelog

All notable changes to herdr-which-key will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

### Added
- **Installed plugins appear in the menu**: press `P` to see every other plugin's panes and actions, discovered from `herdr plugin list --json` when the menu opens. Items are launched after the menu closes, since herdr refuses to open a popup while another popup is open. An explicit `P` in `keys.toml` takes precedence

## [0.1.1]

### Fixed
- **Arrow keys did nothing in pickers**: the up/down arrows are now recognised alongside `j`/`k` when choosing a workspace, tab, or agent. Escape sequences are also read up to their final byte, so a key typed right after an arrow is no longer swallowed

## [0.1.0]

First release.

### Added
- Community standards: contributing guide, security policy, issue and PR templates, code owners, and CI on Python 3.8 and the latest 3.x
- Neovim-style which-key popup: press a leader key, see every next key, drill into groups, run a herdr action
- Default key tree in `keys.toml`, overridable from the plugin config directory
- Text prompts, workspace/tab/agent pickers, and hydra-style repeat (`stay = true`)
