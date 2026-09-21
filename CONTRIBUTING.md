# Contributing

## Setup

```sh
git clone https://github.com/pradyb/herdr-which-key
cd herdr-which-key
herdr plugin link "$PWD"   # use your checkout as the installed plugin
```

Bind the plugin's `open` action to a key as described in the README, then edit
`whichkey.py` or `keys.toml` and try it in a real herdr session.

## Before opening a PR

```sh
python3 test_whichkey.py
python3 -m py_compile whichkey.py
shellcheck launch.sh
```

CI runs the same checks on Python 3.8 and the latest 3.x for every push and PR.

## Guidelines

- Keep the plugin dependency-free (Python standard library only, 3.8+).
- Add a check to `test_whichkey.py` for any new `keys.toml` field or argument-handling behaviour.
- Update the README and the `keys.toml` header comments if you change user-facing behaviour.
- Bump `version` in `herdr-plugin.toml` and add an entry to `CHANGELOG.md` for any change users would notice.
- Never build a shell string from prompted or picked values. `run` entries are passed as argv, and `shell` entries are shell-quoted per value.

## Questions

For usage questions or half-formed ideas, use
[Discussions](https://github.com/pradyb/herdr-which-key/discussions) rather than
the issue tracker. Issues are for reproducible bugs and concrete feature requests.
