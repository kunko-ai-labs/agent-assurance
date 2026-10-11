"""Claude Code `Bash(...)` rules: what counts as a read-only shell grant.

A rule is a read only if every command it can let through only reads. A
command on the read-only list is not enough: `find -exec`, `env <cmd>` and
`git diff --output=<file>` run programs or write files. Deny by default:
anything the classifier cannot prove harmless is execute.
"""

from __future__ import annotations

import pytest

from agent_assurance import policy
from agent_assurance.manifest import ToolAccess
from agent_assurance.scan import scan_directory
from agent_assurance.scan.claude_settings import _bash_class, ignored_policy_entries


@pytest.fixture(autouse=True)
def _default_policy():
    policy.reset()
    yield
    policy.reset()


# Every dangerous form must be execute.
DANGEROUS = [
    # find: runs a program, deletes, or writes a file
    "find . -exec rm {} +",
    "find . -execdir sh -c x {} +",
    "find . -ok rm {} ;",
    "find . -okdir rm {} ;",
    "find . -name x -delete",
    "find . -fprint out.txt",
    "find . -fprint0 out.txt",
    "find . -fprintf out.txt %p",
    "find . -fls out.txt",
    'find . "-exec" rm {} +',  # quoted
    "find . -ex''ec rm {} +",  # quote-split
    "find . -name a:b -delete",  # a colon must not truncate the command
    "find:*",  # prefix rule lets any of the above through
    "find *",
    "find . -name *",
    # env runs any command
    "env:*",
    "env rm -rf x",
    "env -i sh",
    "env FOO=1 sh",
    # git diff / log / show write files with --output
    "git diff --output=x",
    "git diff --output x",
    "git diff --outp=x",  # abbreviated long option
    "git diff --ext-diff",
    "git diff:*",
    "git diff *",
    "git log -p --output=x",
    "git log:*",
    "git show --output=x HEAD",
    "git show:*",
    "git log --show-signature",
    # git branch creates, deletes, renames, edits
    "git branch newname",
    "git branch -D main",
    "git branch -d main",
    "git branch -m a b",
    "git branch --edit-description",
    "git branch --set-upstream-to=origin/x",
    "git branch:*",
    # rg runs a preprocessor or a hostname program; -z spawns decompressors
    "rg --pre sh x",
    "rg --pre=sh x",
    "rg --hostname-bin=sh x",
    "rg -z x",
    "rg:*",
    # fd runs a program per result
    "fd -x rm",
    "fd --exec rm",
    "fd --exec=rm",
    "fd -X rm",
    "fd --exec-batch rm",
    "fd -Hx rm",  # combined short flags
    "fd:*",
    # tree and file write files
    "tree -o out.txt",
    "tree -R -H .",
    "tree:*",
    "file -C -m magic",
    "file --compile",
    "file:*",
    # less: pager with shell escapes, startup commands, log files
    "less:*",
    "less x",
    "less -o log x",
    "less +!rm x",
    # shell operators, redirections and substitutions after a read-only command
    "ls ; rm -rf x",
    "ls && rm -rf x",
    "ls || rm -rf x",
    "cat a | sh",
    "cat a > ~/.bashrc",
    "cat a >> x",
    "cat < x",
    "echo $(rm -rf x)",
    "echo `rm -rf x`",
    "echo $HOME",
    "ls &",
    "ls\nrm -rf x",
    "grep x (rm)",
    # wrappers and interpreters never read
    "xargs rm",
    "sh -c ls",
    "bash -c ls",
    "awk {system(x)}",
    "sed -i s/a/b/ x",
    "sudo ls",
    "nohup ls",
    "timeout 1 ls",
    # not the listed command
    "/usr/bin/find . -delete",
    "FOO=1 git log",
    "git -C x log --output=y",
    "git -c core.pager=sh log",
    "git --exec-path=x log",
    # found by the adversarial review: shell expansion and attached option values
    "find . {-delete,-print}",  # brace expansion produces -delete
    "find . -name x ?delete",  # a file named -delete in the directory matches
    "find . [-]delete",
    "git branch -m5",  # -m with an attached value renames the branch
    "git branch -M5",
    "git branch -C3",  # copies the branch
    "git branch -c3",
    "git branch -l newname",  # -l created a branch in older git
    "env -C5",
    "env -0",
    'find . -name x "-delete"',
    "find\t.\t-delete",
    '"git diff" --output=x',
    "git log -- --output=x",
    "git log -n5 --output=x",
    'find . -name "x',  # unbalanced quote
    "",
]

# Genuine read-only forms keep passing.
READ_ONLY = [
    "git status:*",
    "git status",
    "grep:*",
    "ls:*",
    "ls *",
    "ls -la",
    "cat:*",
    "head:*",
    "tail -f x",
    "wc -l x",
    "echo hi",
    "pwd",
    "which python",
    "type ls",
    "printenv:*",
    "stat x",
    "diff a b",
    "diff:*",
    "git blame:*",
    "gh pr view:*",
    "gh pr list:*",
    "gh issue view:*",
    "gh issue list:*",
    "gh run list:*",
    "gh run view:*",
    "env",
    "find . -name x -type f",
    "find . -maxdepth 2 -mtime -7 -print",
    "find . ! -name x",
    "find",
    "fd -H -t f x",
    "fd --type=f x",
    "rg -n -i foo src",
    "rg --type=py foo",
    "rg -A3 foo",
    "tree -L 2 -a",
    "file -b --mime-type x",
    "git diff",
    "git diff --stat HEAD~1",
    "git diff --cached --name-only -- src",
    "git log --oneline -n 5",
    "git log --format=%H -10",
    "git show --stat HEAD",
    "git branch",
    "git branch -a -vv",
    "git branch --show-current",
    "git branch --list feat/x",
]


@pytest.mark.parametrize("spec", DANGEROUS)
def test_dangerous_form_is_not_read_only(spec):
    access, _scoped = _bash_class(spec)
    assert access is ToolAccess.EXECUTE, spec


@pytest.mark.parametrize("spec", READ_ONLY)
def test_genuine_read_only_form_is_read(spec):
    access, scoped = _bash_class(spec)
    assert (access, scoped) == (ToolAccess.READ, True), spec


def test_unscoped_bash_is_unscoped_execute():
    assert _bash_class(None) == (ToolAccess.EXECUTE, False)
    assert _bash_class("*") == (ToolAccess.EXECUTE, False)


def test_policy_cannot_make_a_dangerous_command_read_only():
    policy.activate(policy.Policy(read_only_commands=["env", "find", "less", "xargs", "git log --oneline", "sh"]))
    for spec in ("env:*", "find:*", "find . -delete", "less:*", "xargs:*", "git log --oneline:*", "sh:*"):
        assert _bash_class(spec)[0] is ToolAccess.EXECUTE, spec


def test_policy_entries_still_extend_the_list():
    policy.activate(policy.Policy(read_only_commands=["poetry run pytest", "make lint"]))
    assert _bash_class("poetry run pytest:*") == (ToolAccess.READ, True)
    assert _bash_class("make lint") == (ToolAccess.READ, True)
    # still no shell operators through a policy entry
    assert _bash_class("make lint && rm -rf x")[0] is ToolAccess.EXECUTE


def test_scan_reports_dangerous_allow_rules_as_execute(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text(
        '{"permissions": {"allow": ["Bash(find:*)", "Bash(env:*)", "Bash(git diff:*)"]}}', encoding="utf-8"
    )
    tools = scan_directory(str(tmp_path)).observed.tools
    assert [(t.type, t.scoped, t.approval) for t in tools] == [(ToolAccess.EXECUTE, True, "auto")]


def test_a_rule_the_parser_does_not_understand_is_unknown_not_dropped(tmp_path):
    """An allow rule must never vanish from the report because it failed to parse."""
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text(
        '{"permissions": {"allow": ["Bash(ls", "Bash (rm -rf x)", "Bash(ls\\nrm -rf x)"]}}', encoding="utf-8"
    )
    result = scan_directory(str(tmp_path))
    kinds = sorted((str(t.type), t.name) for t in result.observed.tools)
    assert len(result.observed.tools) >= 2, kinds
    assert not any(t.type is ToolAccess.READ for t in result.observed.tools), kinds
    assert sum(t.type is ToolAccess.UNKNOWN for t in result.observed.tools) == 2  # the two malformed rules


def test_hyphenated_mcp_server_rule_is_observed(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text('{"permissions": {"allow": ["mcp__my-server__write_file"]}}', encoding="utf-8")
    tools = scan_directory(str(tmp_path)).observed.tools
    assert tools and tools[0].type is ToolAccess.UNKNOWN


# Independent review, round 2: the policy path must not re-mark what the
# built-in lists refuse. The policy file is discovered in the scanned tree, so
# one change can bring both the rule and the entry.
POLICY_BYPASS = [
    ("/usr/bin/env", "/usr/bin/env:*"),
    ("/usr/bin/env", "/usr/bin/env sh -c x"),
    ("/bin/sh", "/bin/sh:*"),
    ("/usr/bin/sed", "/usr/bin/sed:*"),
    ("python3.12", "python3.12:*"),
    ("pip3", "pip3 install x"),
    ("perl5.36", "perl5.36:*"),
    ("ENV", "ENV sh"),  # case-insensitive file systems
    ("git", "git -c core.pager=sh log"),
    ("git", "git push:*"),
    ("git", "git --exec-path=x log"),
    ("gh", "gh api -X DELETE x"),
    ("gh pr", "gh pr merge 1"),
    ("/usr/bin/find", "/usr/bin/find . -delete"),
    ("./find", "./find:*"),  # a repo script named like a built-in is not the built-in
    ("man", "man:*"),
    ("tar", "tar --to-command=sh -xf x"),
    ("busybox", "busybox sh"),
    ("stdbuf", "stdbuf -o0 sh"),
    ("setsid", "setsid sh"),
    ("parallel", "parallel sh ::: x"),
    ("script", "script -c sh"),
    ("strace", "strace sh"),
    ("chroot", "chroot / sh"),
    ("flock", "flock x sh"),
    ("ionice", "ionice sh"),
    ("taskset", "taskset 1 sh"),
    ("unbuffer", "unbuffer sh"),
    ("systemd-run", "systemd-run sh"),
    ("ex", "ex x"),
    ("view", "view x"),
    ("open", "open x"),
    ("xdg-open", "xdg-open x"),
    ("npx", "npx x"),
    ("pip", "pip install x"),
]


@pytest.mark.parametrize("entry,spec", POLICY_BYPASS)
def test_policy_entry_cannot_re_mark_a_refused_command(entry, spec):
    policy.activate(policy.Policy(read_only_commands=[entry]))
    assert _bash_class(spec)[0] is ToolAccess.EXECUTE, (entry, spec)


@pytest.mark.parametrize("spec", ["/usr/bin/env:*", "/bin/sh:*", "python3.12:*", "/usr/bin/find . -name x", "./ls:*", "git -C x status"])
def test_paths_and_versioned_names_are_not_built_in_reads(spec):
    assert _bash_class(spec)[0] is ToolAccess.EXECUTE, spec


def test_explicit_policy_entries_that_widen_nothing_still_work():
    policy.activate(policy.Policy(read_only_commands=["git rev-parse", "make lint", "poetry run pytest", "my_tool-2"]))
    assert _bash_class("git rev-parse:*") == (ToolAccess.READ, True)
    assert _bash_class("make lint:*") == (ToolAccess.READ, True)
    assert _bash_class("poetry run pytest") == (ToolAccess.READ, True)
    assert _bash_class("my_tool-2:*") == (ToolAccess.READ, True)
    assert ignored_policy_entries() == []


# Independent review, round 3: the policy path is deny by default. An entry
# counts only if its command is a plain ASCII name outside the refused
# families; anything else is ignored and reported.
POLICY_BYPASS_3 = [
    ("env*", "env*"),
    ("find*", "find*"),
    ("sh*", "sh*"),
    ("\u017fh", "\u017fh:*"),  # long s: case-insensitive file systems resolve it to sh
    ("\u017fh", "\u017fh -c x"),
    ("python3-dbg", "python3-dbg:*"),
    ("python3.12d", "python3.12d:*"),
    ("pythonw", "pythonw:*"),
    ("nodejs", "nodejs:*"),
    ("env.exe", "env.exe:*"),
    ("find.exe", "find.exe:*"),
    ("git.exe", "git.exe -c core.pager=sh log"),
    ("pypy3", "pypy3:*"),
    ("deno", "deno run x"),
    ("bun", "bun x"),
    ("ruby3.2", "ruby3.2:*"),
    ("irb", "irb:*"),
    ("perl5.36", "perl5.36:*"),
    ("php8", "php8:*"),
    ("lua5.4", "lua5.4:*"),
    ("tclsh8.6", "tclsh8.6:*"),
    ("osascript", "osascript:*"),
    ("rbash", "rbash:*"),
    ("busybox", "busybox:*"),
    ("timeout", "timeout:*"),
    ("fdfind", "fdfind -x rm"),  # Debian's name for fd
    ("findutils-find", "findutils-find:*"),
    ("git diff --output=x", "git diff --output=x"),  # never widens a checked command
    ("find . -delete", "find . -delete"),
    ("rg --pre=sh", "rg --pre=sh x"),
    ("env sh", "env sh"),
]


@pytest.mark.parametrize("entry,spec", POLICY_BYPASS_3)
def test_policy_is_deny_by_default(entry, spec):
    policy.activate(policy.Policy(read_only_commands=[entry]))
    assert _bash_class(spec)[0] is ToolAccess.EXECUTE, (entry, spec)
    assert [e for e, _ in ignored_policy_entries()] == [entry]  # reported, not silently dropped


@pytest.mark.parametrize("spec", ["\u017fh:*", "\uff25\uff2e\uff36 sh", "git.exe status", "ls.exe:*", "LS:*", "Git status"])
def test_non_plain_command_words_are_execute(spec):
    assert _bash_class(spec)[0] is ToolAccess.EXECUTE, spec


def test_ignored_policy_entries_are_reported_by_validate_and_scan(tmp_path, capsys):
    pol = tmp_path / "agent-assurance.policy.yaml"
    pol.write_text("apiVersion: agent-assurance/policy/v1\nname: t\nread_only_commands: [make lint, sh*]\n", encoding="utf-8")
    from agent_assurance import cli

    cli.main(["validate", str(pol)])
    out = capsys.readouterr().out
    assert "read_only_commands entry 'sh*' ignored" in out
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text('{"permissions": {"allow": ["Bash(sh*)"]}}', encoding="utf-8")
    policy.activate(policy.load(str(pol)))
    result = scan_directory(str(tmp_path))
    assert "read_only_commands entry 'sh*' ignored" in (result.sources[0].note or "")
    assert result.observed.tools[0].type is ToolAccess.EXECUTE
