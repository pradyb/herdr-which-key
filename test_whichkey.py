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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
