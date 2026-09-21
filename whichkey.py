#!/usr/bin/env python3
"""which-key popup for herdr.

Runs inside a herdr plugin popup. Shows the available keys, walks into
groups as you type, and runs herdr CLI commands for the leaf you pick.
Standard library only (Python 3.8+).
"""

import json
import os
import re
import select
import shlex
import shutil
import subprocess
import sys
import termios
import tty

HERE = os.path.dirname(os.path.abspath(__file__))
HERDR = os.environ.get("HERDR_BIN_PATH") or "herdr"

# ----------------------------------------------------------------- config


def _parse_toml_subset(text):
    """Tiny fallback for Pythons without tomllib/tomli.

    Supports what keys.toml needs: [table], [[array-of-tables]],
    key = "string" | 'literal' | number | true/false, and # comments.
    """
    data = {}
    cur = data
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"\[\[\s*([A-Za-z0-9_\-]+)\s*\]\]\s*(#.*)?", line)
        if m:
            cur = {}
            data.setdefault(m.group(1), []).append(cur)
            continue
        m = re.fullmatch(r"\[\s*([A-Za-z0-9_\-]+)\s*\]\s*(#.*)?", line)
        if m:
            cur = data.setdefault(m.group(1), {})
            continue
        m = re.fullmatch(r"([A-Za-z0-9_\-]+)\s*=\s*(.+)", line)
        if not m:
            raise ValueError("line %d: cannot parse: %s" % (lineno, raw))
        key, rest = m.group(1), m.group(2).strip()
        if rest.startswith('"'):
            end = 1
            while end < len(rest):
                if rest[end] == "\\":
                    end += 2
                    continue
                if rest[end] == '"':
                    break
                end += 1
            val = json.loads(rest[: end + 1])
        elif rest.startswith("'"):
            end = rest.index("'", 1)
            val = rest[1:end]
        else:
            tok = rest.split("#", 1)[0].strip()
            if tok in ("true", "false"):
                val = tok == "true"
            else:
                try:
                    val = int(tok)
                except ValueError:
                    val = float(tok)
        cur[key] = val
    return data


def load_toml(path):
    with open(path, "rb") as f:
        raw = f.read()
    try:
        import tomllib  # 3.11+

        return tomllib.loads(raw.decode("utf-8"))
    except ImportError:
        pass
    try:
        import tomli

        return tomli.loads(raw.decode("utf-8"))
    except ImportError:
        return _parse_toml_subset(raw.decode("utf-8"))


def config_path():
    cfg_dir = os.environ.get("HERDR_PLUGIN_CONFIG_DIR")
    if cfg_dir:
        p = os.path.join(cfg_dir, "keys.toml")
        if os.path.isfile(p):
            return p
    return os.path.join(HERE, "keys.toml")


SPECIAL_NAMES = {"space": " ", "tab": "\t", "enter": "\r"}
DISPLAY_NAMES = {" ": "SPC", "\t": "TAB", "\r": "RET"}


def norm_key(tok):
    t = tok.strip()
    low = t.lower()
    if low in SPECIAL_NAMES:
        return SPECIAL_NAMES[low]
    if low.startswith("ctrl+") and len(t) == 6:
        return "ctrl+" + low[5]
    return t


def key_label(k):
    if k in DISPLAY_NAMES:
        return DISPLAY_NAMES[k]
    if k.startswith("ctrl+"):
        return "C-" + k[5:]
    return k


class Node:
    def __init__(self, name=""):
        self.name = name
        self.children = {}  # key -> Node
        self.entry = None  # leaf action dict

    @property
    def is_group(self):
        return self.entry is None


def build_tree(cfg):
    root = Node(cfg.get("settings", {}).get("title", "herdr"))
    for item in cfg.get("key", []):
        seq = item.get("seq", "")
        keys = [norm_key(k) for k in seq.split(" ") if k != ""]
        if not keys:
            continue
        node = root
        for k in keys[:-1]:
            node = node.children.setdefault(k, Node(k))
        last = keys[-1]
        child = node.children.setdefault(last, Node(last))
        if "group" in item:
            child.name = item["group"]
        else:
            child.entry = item
            child.name = item.get("desc", item.get("run", item.get("shell", "?")))
    return root


# ----------------------------------------------------------------- context


def load_context():
    ctx = {}
    try:
        ctx = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON") or "{}")
    except ValueError:
        ctx = {}

    def pick(*vals):
        for v in vals:
            if v:
                return v
        return ""

    return {
        "pane": pick(os.environ.get("WK_PANE"), ctx.get("focused_pane_id"), os.environ.get("HERDR_PANE_ID")),
        "tab": pick(os.environ.get("WK_TAB"), ctx.get("tab_id"), os.environ.get("HERDR_TAB_ID")),
        "workspace": pick(
            os.environ.get("WK_WORKSPACE"), ctx.get("workspace_id"), os.environ.get("HERDR_WORKSPACE_ID")
        ),
        "cwd": pick(ctx.get("focused_pane_cwd"), ctx.get("workspace_cwd")),
        "workspace_label": ctx.get("workspace_label") or "",
        "tab_label": ctx.get("tab_label") or "",
    }


PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def fill(text, values):
    return PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), m.group(0))), text)


def build_argv(template, values):
    """Split first, substitute per token, so user input never re-splits.

    A `--flag {x}` pair is dropped when {x} is empty, so optional values
    like --cwd disappear instead of becoming an empty argument.
    """
    out = []
    for tok in shlex.split(template):
        names = PLACEHOLDER.findall(tok)
        filled = fill(tok, values)
        if names and filled == "":
            if out and out[-1].startswith("--"):
                out.pop()
            continue
        out.append(filled)
    return out


# ----------------------------------------------------------------- herdr


def herdr_json(args):
    p = subprocess.run([HERDR] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip() or "herdr %s failed" % " ".join(args))
    return json.loads(p.stdout)


def _find_list(obj, key):
    if isinstance(obj, dict):
        if isinstance(obj.get(key), list):
            return obj[key]
        for v in obj.values():
            r = _find_list(v, key)
            if r is not None:
                return r
    return None


def pick_items(kind, values):
    """Return [(id, label, focused)] for a picker."""
    if kind == "workspace":
        rows = _find_list(herdr_json(["workspace", "list"]), "workspaces") or []
        return [
            (w["workspace_id"], w.get("label") or w["workspace_id"], w.get("focused", False))
            for w in rows
        ]
    if kind == "tab":
        args = ["tab", "list"] + (["--workspace", values["workspace"]] if values.get("workspace") else [])
        rows = _find_list(herdr_json(args), "tabs") or []
        return [(t["tab_id"], t.get("label") or t["tab_id"], t.get("focused", False)) for t in rows]
    if kind == "agent":
        rows = _find_list(herdr_json(["agent", "list"]), "agents") or []
        items = []
        for a in rows:
            name = a.get("name") or a.get("display_agent") or a.get("agent") or "agent"
            status = a.get("agent_status", "")
            items.append((a["pane_id"], "%-14s %-8s %s" % (name, status, a.get("pane_id", "")), a.get("focused", False)))
        return items
    raise RuntimeError("unknown pick kind: %s" % kind)


# ----------------------------------------------------------------- terminal

ESC = "\x1b"
C_RESET = ESC + "[0m"
C_DIM = ESC + "[2m"
C_BOLD = ESC + "[1m"
C_KEY = ESC + "[1;33m"  # yellow keys
C_GROUP = ESC + "[1;35m"  # magenta groups
C_ACC = ESC + "[36m"  # cyan accents
C_ERR = ESC + "[1;31m"


class Term:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old = termios.tcgetattr(self.fd)

    def __enter__(self):
        tty.setraw(self.fd)
        self.write(ESC + "[?25l")  # hide cursor
        return self

    def __exit__(self, *exc):
        self.write(ESC + "[?25h" + C_RESET)
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    def write(self, s):
        os.write(sys.stdout.fileno(), s.encode("utf-8"))

    def size(self):
        s = shutil.get_terminal_size((80, 16))
        return s.columns, s.lines

    def read_key(self):
        """Return one key: a character, 'esc', 'backspace', 'ctrl+x', or ''."""
        b = os.read(self.fd, 1)
        if not b:
            return "esc"
        if b == b"\x1b":
            # lone ESC vs. an escape sequence (arrows etc.)
            r, _, _ = select.select([self.fd], [], [], 0.03)
            if not r:
                return "esc"
            os.read(self.fd, 16)  # swallow the sequence
            return ""
        if b in (b"\x7f", b"\x08"):
            return "backspace"
        if b in (b"\r", b"\n"):
            return "\r"
        if b == b"\t":
            return "\t"
        if b == b"\x03":
            return "esc"  # ctrl+c closes
        if b[0] < 32:
            return "ctrl+" + chr(b[0] + 96)
        # utf-8 continuation bytes
        first = b[0]
        extra = 1 if first >= 0xC0 else 0
        extra = 2 if first >= 0xE0 else extra
        extra = 3 if first >= 0xF0 else extra
        if extra:
            b += os.read(self.fd, extra)
        return b.decode("utf-8", "replace")


def visible_len(s):
    return len(re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s))


def truncate(s, n):
    return s if len(s) <= n else s[: max(0, n - 1)] + "…"


class UI:
    def __init__(self, term, title):
        self.t = term
        self.title = title

    def frame(self, crumbs, body_lines, footer):
        cols, rows = self.t.size()
        out = [ESC + "[H" + ESC + "[2J"]
        head = " " + C_ACC + C_BOLD + self.title + C_RESET
        for c in crumbs:
            head += C_DIM + " › " + C_RESET + C_GROUP + c + C_RESET
        out.append(head)
        out.append(C_DIM + "─" * max(0, cols) + C_RESET)
        avail = max(1, rows - 4)
        for line in body_lines[:avail]:
            out.append(line)
        pad = avail - min(len(body_lines), avail)
        out.extend([""] * pad)
        out.append(C_DIM + " " + footer + C_RESET)
        self.t.write("\r\n".join(out))

    def menu(self, node, crumbs, message=""):
        cols, _ = self.t.size()
        items = sorted(node.children.items(), key=lambda kv: (kv[1].is_group, kv[0].lower(), kv[0].isupper()))
        cells = []
        for k, child in items:
            if child.is_group:
                cells.append((key_label(k), C_GROUP + "+" + child.name + C_RESET, len(child.name) + 1))
            else:
                d = child.name
                cells.append((key_label(k), d, len(d)))
        if not cells:
            body = [C_DIM + "  (empty group)" + C_RESET]
        else:
            klen = max(len(c[0]) for c in cells)
            cell_w = min(max(klen + 4 + c[2] for c in cells) + 3, max(20, cols - 2))
            ncols = max(1, (cols - 2) // cell_w)
            nrows = (len(cells) + ncols - 1) // ncols
            body = []
            for r in range(nrows):
                line = " "
                for c in range(ncols):
                    i = c * nrows + r  # column-major, like which-key
                    if i >= len(cells):
                        break
                    k, desc, dlen = cells[i]
                    room = cell_w - klen - 5
                    if dlen > room:
                        plain = re.sub(r"\x1b\[[0-9;]*m", "", desc)
                        desc = truncate(plain, room)
                        dlen = len(desc)
                    txt = " " + C_KEY + k.rjust(klen) + C_RESET + C_DIM + " → " + C_RESET + desc
                    line += txt + " " * max(0, cell_w - visible_len(txt))
                body.append(line.rstrip())
        if message:
            body = [" " + message, ""] + body
        footer = "esc close" + ("  ⌫ back" if crumbs else "")
        self.frame(crumbs, body, footer)

    def prompt(self, crumbs, label, default=""):
        buf = default
        while True:
            body = ["", " " + C_BOLD + label + C_RESET, "", " " + C_ACC + "› " + C_RESET + buf + C_KEY + "▏" + C_RESET]
            self.frame(crumbs, body, "enter confirm  esc cancel  C-u clear")
            k = self.t.read_key()
            if k == "esc":
                return None
            if k == "\r":
                return buf
            if k == "backspace":
                buf = buf[:-1]
            elif k == "ctrl+u":
                buf = ""
            elif k == "ctrl+w":
                buf = re.sub(r"\S*\s*$", "", buf)
            elif k and len(k) == 1 and (k >= " "):
                buf += k

    def choose(self, crumbs, label, items):
        if not items:
            self.message(crumbs, C_ERR + "nothing to pick" + C_RESET)
            return None
        keys = "123456789abcdefghijklmnopqrstuvwxyz"
        sel = next((i for i, it in enumerate(items) if it[2]), 0)
        while True:
            body = [" " + C_BOLD + label + C_RESET, ""]
            for i, (_id, text, focused) in enumerate(items):
                k = keys[i] if i < len(keys) else " "
                mark = C_ACC + "▸" + C_RESET if i == sel else " "
                cur = C_DIM + " (current)" + C_RESET if focused else ""
                body.append(" %s %s%s%s %s%s" % (mark, C_KEY, k, C_RESET, text, cur))
            self.frame(crumbs, body, "key or j/k + enter  esc cancel")
            k = self.t.read_key()
            if k == "esc":
                return None
            if k == "\r":
                return items[sel][0]
            if k in ("j", "ctrl+n"):
                sel = (sel + 1) % len(items)
                continue
            if k in ("k", "ctrl+p"):
                sel = (sel - 1) % len(items)
                continue
            if k and k in keys[: len(items)] and k not in ("j", "k"):
                return items[keys.index(k)][0]

    def message(self, crumbs, text):
        self.frame(crumbs, ["", " " + text], "any key to continue")
        self.t.read_key()


# ----------------------------------------------------------------- actions


def run_entry(ui, entry, crumbs, ctx):
    """Execute a leaf. Returns (ok, error_text)."""
    values = dict(ctx)
    if entry.get("pick"):
        try:
            items = pick_items(entry["pick"], values)
        except Exception as e:  # noqa: BLE001
            return False, str(e)
        chosen = ui.choose(crumbs, entry.get("desc", "pick"), items)
        if chosen is None:
            return None, ""
        values["pick"] = chosen
    if entry.get("prompt"):
        text = ui.prompt(crumbs, entry["prompt"], fill(entry.get("default", ""), values))
        if text is None:
            return None, ""
        values["input"] = text

    if entry.get("shell"):
        env = dict(os.environ)
        for k, v in values.items():
            env["WK_" + k.upper()] = str(v)
        cmd = fill(entry["shell"], {k: shlex.quote(str(v)) for k, v in values.items()})
        p = subprocess.run(["sh", "-c", cmd], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    elif entry.get("run"):
        argv = [HERDR] + build_argv(entry["run"], values)
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    else:
        return False, "entry has no run/shell command"
    if p.returncode != 0:
        err = (p.stderr or p.stdout).strip()
        try:
            j = json.loads(err)
            err = j.get("error", {}).get("message") or err
        except ValueError:
            pass
        return False, err or "command failed (exit %d)" % p.returncode
    return True, ""


def main():
    if not sys.stdin.isatty():
        print("which-key must run in a herdr popup (bind pradyb.which-key.open to a key)")
        return 1
    path = config_path()
    try:
        cfg = load_toml(path)
        root = build_tree(cfg)
    except Exception as e:  # noqa: BLE001
        with Term() as t:
            UI(t, "which-key").message([], C_ERR + "config error in %s: %s" % (path, e) + C_RESET)
        return 1
    ctx = load_context()

    with Term() as t:
        ui = UI(t, root.name)
        stack = [root]
        msg = ""
        while True:
            node = stack[-1]
            crumbs = [n.name for n in stack[1:]]
            ui.menu(node, crumbs, msg)
            msg = ""
            k = t.read_key()
            if k == "esc":
                return 0
            if k == "backspace":
                if len(stack) > 1:
                    stack.pop()
                continue
            if not k:
                continue
            child = node.children.get(k)
            if child is None:
                msg = C_DIM + "no binding for " + C_RESET + C_KEY + key_label(k) + C_RESET
                continue
            if child.is_group:
                stack.append(child)
                continue
            ok, err = run_entry(ui, child.entry, crumbs + [child.name], ctx)
            if ok is None:  # cancelled prompt / picker
                continue
            if not ok:
                ui.message(crumbs, C_ERR + "✗ " + C_RESET + err)
                continue
            if child.entry.get("stay"):
                msg = C_ACC + "✓ " + C_RESET + child.name
                continue
            return 0


if __name__ == "__main__":
    sys.exit(main())
