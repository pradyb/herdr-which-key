# herdr which-key

A Neovim/tmux-style **which-key** popup for [herdr](https://herdr.dev).
Press one leader key, see every next key with a label, and drill into
groups until you hit an action.

```
 herdr › pane
──────────────────────────────────────────────────────────────
  h → focus left       K → swap up          t → move pane to new tab
  H → swap left        l → focus right      v → split right
  j → focus down       L → swap right       x → close pane
  J → swap down        r → rename pane      z → zoom toggle
  k → focus up         s → split down       R → +resize (repeat)

 esc close  ⌫ back
```

## Requirements

- herdr 0.7.4 or newer (the version that added popups)
- `python3` on your PATH. It only uses the standard library, so any Python 3.8+ works.
- Linux or macOS

## Install

```sh
herdr plugin install pradyb/herdr-which-key
```

herdr shows a preview of the manifest and the commands it will run before installing.

Then bind a leader key in `~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "prefix+space"            # or "ctrl+space" for a direct, prefix-free leader
type = "plugin_action"
command = "pradyb.which-key.open"
description = "which-key"
```

and apply it:

```sh
herdr server reload-config
```

To update, run the install command again. Your `keys.toml` lives in the plugin config dir, so updating doesn't overwrite it.

### From a local checkout (for development)

```sh
git clone https://github.com/pradyb/herdr-which-key
herdr plugin link "$PWD/herdr-which-key"
```

## Default map

| Keys | Action |
|---|---|
| `\|` / `-` | split right / down |
| `z` | zoom toggle |
| `SPC` | switch workspace (picker) |
| `a` | jump to agent (picker) |
| `R` | reload herdr config |
| `w` n N s r x | workspace: new, new named, switch, rename, close |
| `t` n N s r x | tab: new, new named, switch, rename, close |
| `p` v s z r x t | pane: split right/down, zoom, rename, close, move to new tab |
| `p` h j k l | focus pane |
| `p` H J K L | swap pane |
| `p R` h j k l | resize, stays open so you can tap repeatedly |
| `g n` | new git worktree (asks for a branch) |

In the popup: `esc` closes it, `backspace` goes up a level, and pickers
accept `1-9 a-z` or `j/k` + `enter`.

## Customise

```sh
cp keys.toml "$(herdr plugin config-dir pradyb.which-key)/keys.toml"
$EDITOR "$(herdr plugin config-dir pradyb.which-key)/keys.toml"
```

Changes apply the next time the popup opens, with no reload needed. Each entry:

```toml
[[key]]
seq = "t"               # a group
group = "tab"

[[key]]
seq = "t r"             # keys, space separated
desc = "rename tab"
prompt = "Rename tab"   # optional: ask for text -> {input}
default = "{tab_label}"
run = "tab rename {tab} {input}"   # herdr CLI args

[[key]]
seq = "o"
desc = "new tab (via shell)"
shell = "herdr tab create --cwd {cwd} --focus"   # any shell command

[[key]]
seq = "p R l"
desc = "grow right"
stay = true             # hydra mode: menu stays open
run = "pane resize --direction right --amount 0.05 --pane {pane}"
```

- `pick = "workspace" | "tab" | "agent"` shows a picker first and puts the chosen id in `{pick}`.
- Placeholders: `{pane} {tab} {workspace} {cwd} {workspace_label} {tab_label} {input} {pick}`.
- If a placeholder is empty, it is dropped along with the `--flag` just before it. So `--cwd {cwd}` simply disappears when there is no cwd.
- Special keys in `seq`: `space`, `tab`, `enter`, `ctrl+x`.
- Popup size can't be set in `keys.toml`. Edit `width` / `height` on the
  `[[panes]]` entry in the plugin's own `herdr-plugin.toml` (default `70%` × `16`).
  An install from GitHub is a managed checkout, so a reinstall resets this edit.
  To keep a custom size, use a local clone with `herdr plugin link`. If the new
  size doesn't show up, unlink and link the plugin again so herdr re-reads the manifest.

See the [herdr CLI reference](https://herdr.dev/docs/cli-reference/) for everything `run` can call.

## Troubleshooting

- **Nothing happens:** run `herdr plugin log list --plugin pradyb.which-key`.
- **`ui_busy`:** a popup can't open while Settings, copy mode, or another modal is active.
- Detach (`prefix q`) and a few other built-ins have no CLI command, so they can't be put in the menu. Keep using their normal keys.

## Contributing

Issues and PRs are welcome at <https://github.com/pradyb/herdr-which-key>.

## License

[MIT](LICENSE)
