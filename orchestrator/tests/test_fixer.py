"""
Tests for fixer_node's diff-only file scoping (see nodes/fixer.py and
config.py's DIFF_ONLY_MODE). Covers _extract_changed_files against real git
diff output shapes — modified, new, deleted, and renamed files — since that
parsing is what determines which files Edit gets scoped to. Also covers
fixer_node's mode-switching (allowedTools/prompt construction) with
run_claude_code mocked out, since these tests shouldn't make a real Claude
Code call.
"""
import nodes.fixer as fixer_module
from config import settings
from nodes.fixer import _extract_changed_files, fixer_node

MODIFIED_FILE_DIFF = """\
diff --git a/app.py b/app.py
index abc123..def456 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
-old line
+new line
 unchanged line
"""

NEW_FILE_DIFF = """\
diff --git a/new_file.py b/new_file.py
new file mode 100644
index 0000000..abc123
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1 @@
+content
"""

DELETED_FILE_DIFF = """\
diff --git a/old_file.py b/old_file.py
deleted file mode 100644
index abc123..0000000
--- a/old_file.py
+++ /dev/null
"""

RENAMED_FILE_DIFF = """\
diff --git a/old/path.py b/new/path.py
similarity index 100%
rename from old/path.py
rename to new/path.py
"""


def test_extracts_path_from_modified_file_diff():
    assert _extract_changed_files(MODIFIED_FILE_DIFF) == ["app.py"]


def test_extracts_path_from_new_file_diff():
    assert _extract_changed_files(NEW_FILE_DIFF) == ["new_file.py"]


def test_extracts_path_from_deleted_file_diff():
    assert _extract_changed_files(DELETED_FILE_DIFF) == ["old_file.py"]


def test_extracts_new_path_from_renamed_file_diff():
    assert _extract_changed_files(RENAMED_FILE_DIFF) == ["new/path.py"]


def test_extracts_multiple_files_in_order():
    combined = MODIFIED_FILE_DIFF + NEW_FILE_DIFF
    assert _extract_changed_files(combined) == ["app.py", "new_file.py"]


def test_empty_diff_returns_no_files():
    assert _extract_changed_files("") == []


def test_malformed_diff_returns_no_files():
    assert _extract_changed_files("not a real diff\njust some text\n") == []


def _base_state(diff: str) -> dict:
    return {
        "repo_path": "/workspace/fake-run",
        "diff": diff,
        "review_notes": "fix the bug",
        "test_output": "",
        "fix_attempts": 0,
    }


def test_diff_only_mode_off_uses_unscoped_allowed_tools(monkeypatch):
    monkeypatch.setattr(settings, "diff_only_mode", False)
    captured = {}
    monkeypatch.setattr(
        fixer_module, "run_claude_code",
        lambda **kwargs: captured.update(kwargs),
    )

    fixer_node(_base_state(MODIFIED_FILE_DIFF))

    assert captured["allowed_tools"] == "Read,Edit,Bash,Grep,Glob"
    assert "Files changed by the triggering diff" not in captured["prompt"]


def test_diff_only_mode_on_scopes_edit_to_changed_files(monkeypatch):
    monkeypatch.setattr(settings, "diff_only_mode", True)
    captured = {}
    monkeypatch.setattr(
        fixer_module, "run_claude_code",
        lambda **kwargs: captured.update(kwargs),
    )

    fixer_node(_base_state(MODIFIED_FILE_DIFF))

    assert captured["allowed_tools"] == "Read,Bash,Grep,Glob,Edit(app.py)"
    assert "app.py" in captured["prompt"]


def test_diff_only_mode_on_falls_back_when_diff_unparseable(monkeypatch):
    monkeypatch.setattr(settings, "diff_only_mode", True)
    captured = {}
    monkeypatch.setattr(
        fixer_module, "run_claude_code",
        lambda **kwargs: captured.update(kwargs),
    )

    fixer_node(_base_state("not a real diff\n"))

    assert captured["allowed_tools"] == "Read,Edit,Bash,Grep,Glob"
