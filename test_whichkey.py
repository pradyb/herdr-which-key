"""Smoke checks for whichkey.py. Run: python3 test_whichkey.py (stdlib only)."""
import os
import whichkey as wk

KEYS = os.path.join(wk.HERE, "keys.toml")
CTX = {n: "x" for n in "pane tab workspace cwd workspace_label tab_label input pick".split()}


def leaves(node):
    if node.entry:
        yield node
    for child in node.children.values():
        yield from leaves(child)


def test_subset_parser_matches_real_parser():
    with open(KEYS, encoding="utf-8") as f:
        assert wk._parse_toml_subset(f.read()) == wk.load_toml(KEYS)


def test_every_default_entry_builds_a_command():
    found = list(leaves(wk.build_tree(wk.load_toml(KEYS))))
    assert found, "keys.toml has no actions"
    for leaf in found:
        e = leaf.entry
        assert e.get("run") or e.get("shell"), "no command: %s" % e
        if e.get("run"):
            argv = wk.build_argv(e["run"], CTX)
            assert argv and "{" not in "".join(argv), "unfilled placeholder: %s" % e["run"]


def test_user_input_never_resplits():
    got = wk.build_argv("workspace rename {workspace} {input}", {"workspace": "w1", "input": "a b; rm -rf"})
    assert got == ["workspace", "rename", "w1", "a b; rm -rf"]


def test_empty_placeholder_drops_its_flag():
    assert wk.build_argv("tab create --cwd {cwd}", {"cwd": ""}) == ["tab", "create"]


def _keys(raw, n):
    """Feed raw bytes to Term.read_key. The write end is closed so a broken parser hits EOF, not a hang."""
    r, w = os.pipe()
    os.write(w, raw)
    os.close(w)
    t = wk.Term.__new__(wk.Term)  # skip __init__: it needs a real tty
    t.fd = r
    try:
        return [t.read_key() for _ in range(n)]
    finally:
        os.close(r)


def test_arrow_keys_parse_and_do_not_swallow_the_next_key():
    # down, up, app-mode down, ctrl+up, plain j, Delete (ignored), plain x
    assert _keys(b"\x1b[B\x1b[A\x1bOB\x1b[1;5Aj\x1b[3~x", 7) == ["down", "up", "down", "up", "j", "", "x"]


def test_lone_escape_is_esc():
    assert _keys(b"\x1b", 1) == ["esc"]


PLUGINS = [  # shape of `herdr plugin list --json` on herdr 0.9.1
    {"plugin_id": "pradyb.which-key", "name": "Which Key", "enabled": True,
     "actions": [{"id": "open", "title": "Open which-key menu"}], "panes": [{"id": "menu", "title": "Which Key"}]},
    {"plugin_id": "thewtex.mem-cpu-load", "name": "Mem CPU Load", "enabled": True,
     "actions": [{"id": "show-status", "title": "Show system status"}, {"id": "write-config", "title": "Write a default config.toml"}],
     "panes": [{"id": "status", "title": "System status"}]},
    {"plugin_id": "off.plugin", "name": "Off", "enabled": False, "actions": [{"id": "x", "title": "X"}], "panes": []},
]


def _tree_with_plugins(plugins, cfg=None):
    root = wk.build_tree(cfg or {"key": []})
    wk.add_plugins(root, plugins, "pradyb.which-key")
    return root


def test_plugins_group_lists_other_plugins_panes_and_actions():
    root = _tree_with_plugins(PLUGINS)
    group = root.children["P"]
    assert [n.name for n in group.children.values()] == ["Mem CPU Load"]  # not ourselves, not the disabled one
    sub = next(iter(group.children.values()))
    cmds = {leaf.name: wk.build_argv(leaf.entry["run"], CTX) for leaf in sub.children.values()}
    assert cmds["System status"] == ["plugin", "pane", "open", "--plugin", "thewtex.mem-cpu-load", "--entrypoint", "status"]
    assert cmds["Show system status"] == ["plugin", "action", "invoke", "show-status", "--plugin", "thewtex.mem-cpu-load"]
    assert len(sub.children) == 3 and all(leaf.entry["defer"] for leaf in sub.children.values())


def test_plugin_keys_are_unique_even_when_titles_collide():
    labels = ["System status", "Show system status", "Save settings", "Sync"]
    taken = {}
    for label in labels:
        k = wk.pick_key(label, taken)
        assert k and k not in taken
        taken[k] = label
    assert len(taken) == len(labels)


def test_explicit_P_in_keys_toml_wins_and_no_plugins_adds_nothing():
    mine = {"key": [{"seq": "P", "desc": "mine", "run": "server reload-config"}]}
    assert _tree_with_plugins(PLUGINS, mine).children["P"].entry["run"] == "server reload-config"
    assert "P" not in _tree_with_plugins(PLUGINS[:1]).children


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
