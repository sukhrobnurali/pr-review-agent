from __future__ import annotations

from pr_review_agent.tools.git import parse_diff


def test_empty_diff() -> None:
    assert parse_diff("") == []
    assert parse_diff("   \n") == []


def test_single_file_single_hunk() -> None:
    diff = """diff --git a/src/foo.py b/src/foo.py
index 1234567..89abcde 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -10,3 +10,4 @@ class Foo:
     def bar(self):
-        return None
+        return self.baz()
+        # added comment
     def baz(self):
"""
    out = parse_diff(diff)
    assert len(out) == 1
    assert out[0].path == "src/foo.py"
    assert out[0].status == "modified"
    assert len(out[0].hunks) == 1
    h = out[0].hunks[0]
    assert h.new_start == 10
    assert h.new_end == 13
    assert h.old_start == 10
    assert h.old_end == 12


def test_multiple_files() -> None:
    diff = """diff --git a/a.py b/a.py
index aaa..bbb 100644
--- a/a.py
+++ b/a.py
@@ -1,1 +1,1 @@
-x
+y
diff --git a/b.py b/b.py
index ccc..ddd 100644
--- a/b.py
+++ b/b.py
@@ -5,2 +5,3 @@ def f():
     pass
+    return 1
"""
    out = parse_diff(diff)
    assert [c.path for c in out] == ["a.py", "b.py"]


def test_multiple_hunks_in_one_file() -> None:
    diff = """diff --git a/x.py b/x.py
index aaa..bbb 100644
--- a/x.py
+++ b/x.py
@@ -1,2 +1,3 @@
 line1
+inserted at top
 line2
@@ -50,2 +51,3 @@
 line50
+inserted in middle
 line51
"""
    out = parse_diff(diff)
    assert len(out[0].hunks) == 2
    assert out[0].hunks[0].new_start == 1
    assert out[0].hunks[1].new_start == 51


def test_added_line_ranges() -> None:
    diff = """diff --git a/x.py b/x.py
--- a/x.py
+++ b/x.py
@@ -10,2 +10,4 @@
 line10
+a
+b
 line11
"""
    out = parse_diff(diff)
    assert out[0].added_line_ranges == [(10, 13)]


def test_new_file_status() -> None:
    diff = """diff --git a/new.py b/new.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+import os
+print(os.getcwd())
"""
    out = parse_diff(diff)
    assert out[0].status == "added"
    assert out[0].path == "new.py"
    assert out[0].hunks[0].new_start == 1
    assert out[0].hunks[0].new_end == 2


def test_renamed_file() -> None:
    diff = """diff --git a/old.py b/new.py
similarity index 100%
rename from old.py
rename to new.py
"""
    out = parse_diff(diff)
    assert out[0].status == "renamed"
    assert out[0].path == "new.py"
    assert out[0].old_path == "old.py"
    assert out[0].is_renamed


def test_deleted_file() -> None:
    diff = """diff --git a/gone.py b/gone.py
deleted file mode 100644
index 1234567..0000000
--- a/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
-line1
-line2
"""
    out = parse_diff(diff)
    assert out[0].status == "deleted"


def test_single_line_hunk_no_length() -> None:
    diff = """diff --git a/x.py b/x.py
--- a/x.py
+++ b/x.py
@@ -5 +5 @@
-old
+new
"""
    out = parse_diff(diff)
    h = out[0].hunks[0]
    assert h.new_start == 5
    assert h.new_end == 5
