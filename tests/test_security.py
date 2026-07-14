"""Unit tests for ``utils.security`` — path validation, shell sanitization,
output truncation and Discord chunking.

These helpers guard the bot's remote-exec surface, so their behaviour is
security-relevant and worth pinning down.
"""
import os

import pytest

import utils.security as security


# ── validate_project_path ─────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/tmp/projectexo/app", "/opt/service", "/root/x"])
def test_validate_project_path_allows_roots(path):
    result = security.validate_project_path(path)
    # Returns an absolute realpath (may add the /private prefix on macOS),
    # but the final path component is preserved.
    assert os.path.isabs(result)
    assert result.split("/")[-1] == path.split("/")[-1]


def test_validate_project_path_rejects_outside_roots():
    with pytest.raises(ValueError):
        security.validate_project_path("/etc/passwd")


def test_validate_project_path_blocks_traversal_out_of_root():
    # A path that resolves out of every allowed root must be rejected.
    with pytest.raises(ValueError):
        security.validate_project_path("/tmp/../etc/shadow")


def test_validate_project_path_expands_user(monkeypatch):
    monkeypatch.setenv("HOME", "/root")
    # ~ expands to /root which is an allowed root.
    assert security.validate_project_path("~/proj").endswith("/root/proj")


# ── safe_relative ─────────────────────────────────────────────────────────────

def test_safe_relative_ok(tmp_path):
    resolved = security.safe_relative(str(tmp_path), "sub/file.txt")
    assert resolved.endswith("sub/file.txt")


def test_safe_relative_blocks_traversal(tmp_path):
    with pytest.raises(ValueError):
        security.safe_relative(str(tmp_path), "../../etc/passwd")


# ── sanitize_shell_arg ────────────────────────────────────────────────────────

@pytest.mark.parametrize("arg", ["myfile.txt", "some-branch_name", "path/to/dir"])
def test_sanitize_shell_arg_accepts_safe(arg):
    assert security.sanitize_shell_arg(arg) == arg


@pytest.mark.parametrize(
    "arg",
    [
        "a; rm file",
        "a && b",
        "a || b",
        "a | b",
        "`whoami`",
        "$(id)",
        "echo x > /etc/hosts",
        "rm -rf /",
    ],
)
def test_sanitize_shell_arg_rejects_dangerous(arg):
    with pytest.raises(ValueError):
        security.sanitize_shell_arg(arg)


# ── truncate ──────────────────────────────────────────────────────────────────

def test_truncate_short_text_unchanged():
    assert security.truncate("hello", limit=100) == "hello"


def test_truncate_long_text_marks_and_keeps_ends():
    text = "A" * 500 + "B" * 500
    out = security.truncate(text, limit=200)
    assert "truncated" in out
    assert out.startswith("A")
    assert out.endswith("B")
    # The middle content is dropped, so output is shorter than the input.
    assert len(out) < len(text)


def test_truncate_default_limit_used():
    text = "x" * (security.MAX_OUTPUT + 50)
    out = security.truncate(text)
    assert "truncated" in out


# ── chunk_message ─────────────────────────────────────────────────────────────

def test_chunk_message_empty_returns_single_empty():
    assert security.chunk_message("") == [""]


def test_chunk_message_short_single_chunk():
    assert security.chunk_message("line1\nline2\n", size=1900) == ["line1\nline2\n"]


def test_chunk_message_splits_long_text():
    text = "".join(f"line {i}\n" for i in range(1000))
    chunks = security.chunk_message(text, size=200)
    assert len(chunks) > 1
    # No chunk should be wildly larger than the size budget (single lines fit).
    assert all(len(c) <= 200 + 20 for c in chunks)
    # Reassembly is lossless.
    assert "".join(chunks) == text
