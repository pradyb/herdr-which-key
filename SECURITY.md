# Security Policy

## Supported Versions

Only the latest release (and the latest commit on `main`) is actively supported with security fixes.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues privately using
[GitHub's private vulnerability reporting](https://github.com/pradyb/herdr-which-key/security/advisories/new)
or by emailing **pradeep.devlabs@gmail.com**.

Include:
- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept if possible)
- Your suggested fix or mitigation (optional)

You can expect an acknowledgement within **72 hours**.

## How Commands Are Run

`herdr-which-key` runs the commands defined in `keys.toml`, which you control.

- `run` entries are split into arguments first and passed to `herdr` as argv. Values from prompts, pickers, and the focused pane are substituted per argument and never go through a shell.
- `shell` entries run via `sh -c`, with every substituted value shell-quoted. They exist to run whatever you write, so treat a `keys.toml` from someone else like a shell script and read it before use.

## Scope

In scope: any way a prompted, picked, or context value (`{input}`, `{pick}`,
`{pane}`, `{cwd}`, …) can inject extra arguments or shell commands, and any
way the popup can run something that `keys.toml` did not ask for.

Out of scope: commands that a `keys.toml` you chose to use runs on purpose,
and vulnerabilities in herdr itself (report those to the herdr project).
