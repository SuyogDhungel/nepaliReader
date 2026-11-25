# -*- coding: utf-8 -*-
"""Unit tests for Nepali Reader GitHub auto-updater."""

import os
import sys
import unittest

# Add addon path to sys.path
ADDON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "addon", "globalPlugins", "nepaliReader"
)
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

import updater


class TestUpdater(unittest.TestCase):

    def test_parse_version(self):
        self.assertEqual(updater.parseVersion("v2.1.0"), (2, 1, 0))
        self.assertEqual(updater.parseVersion("2.1.1"), (2, 1, 1))
        self.assertEqual(updater.parseVersion("2.0.9"), (2, 0, 9))
        self.assertEqual(updater.parseVersion("v1.1.7-beta"), (1, 1, 7))
        self.assertEqual(updater.parseVersion(""), (0, 0, 0))
        self.assertEqual(updater.parseVersion(None), (0, 0, 0))

        # Comparisons
        self.assertTrue(updater.parseVersion("2.1.1") > updater.parseVersion("2.1.0"))
        self.assertTrue(updater.parseVersion("2.1.0") > updater.parseVersion("2.0.9"))
        self.assertTrue(updater.parseVersion("v2.1.0") > updater.parseVersion("v2.0.9"))
        self.assertFalse(updater.parseVersion("2.1.0") > updater.parseVersion("2.1.0"))

    def test_strip_markdown(self):
        md = """
### Release v2.1.1
- **Feature**: Added updater with live progress.
- `Code` fix for *italics*.
> Some blockquote
---
[Link to somewhere](https://example.com)
```
some code
```
"""
        plain = updater.stripMarkdown(md)
        self.assertNotIn("###", plain)
        self.assertNotIn("**", plain)
        self.assertNotIn("`", plain)
        self.assertNotIn("```", plain)
        self.assertNotIn("---", plain)
        self.assertIn("• Feature: Added updater with live progress.", plain)
        self.assertIn("Code fix for italics.", plain)

    def test_download_task_init(self):
        task = updater.DownloadTask("https://example.com/test.nvda-addon", "2.1.1")
        self.assertEqual(task.url, "https://example.com/test.nvda-addon")
        self.assertEqual(task.newVerStr, "2.1.1")
        self.assertFalse(task.cancelFlag.is_set())
        task.cancelFlag.set()
        self.assertTrue(task.cancelFlag.is_set())

    def test_changelog_since_installed_version(self):
        text = (
            "# Changelog\n\n"
            "## [2.2.0] - 2026-11-25\n- Reads what the document says.\n\n"
            "## [2.1.0] - 2026-10-01\n- Tables.\n\n"
            "## [2.0.9]\n- Old.\n"
        )
        part = updater.changelogSince(text, (2, 0, 9), (2, 2, 0))
        self.assertIn("Reads what the document says", part)
        self.assertIn("Tables", part)
        self.assertNotIn("Old", part)
        notes = updater.releaseNotes("short body", part)
        self.assertTrue(notes.startswith("Version 2.2.0 - 2026-11-25"))
        self.assertEqual(updater.releaseNotes("**Body** only", ""), "Body only")

    def test_angle_brackets_in_text_stay(self):
        plain = updater.stripMarkdown('read "(>) कब्जा गन<"; now "(ख)".<br>\nNext line <b>bold</b>.')
        self.assertEqual(plain, 'read "(>) कब्जा गन<"; now "(ख)".\nNext line bold.')

    def test_markdown_tables_read_as_rows(self):
        plain = updater.stripMarkdown("| | 2.1.0 | 2.2.0 |\n|---|---|---|\n| Words right | 96.9 | 99.9 |")
        self.assertEqual(plain, "2.1.0, 2.2.0\nWords right, 96.9, 99.9")

    def test_check_package(self):
        import tempfile
        import zipfile
        d = tempfile.mkdtemp()
        good = os.path.join(d, "good.nvda-addon")
        with zipfile.ZipFile(good, "w") as z:
            z.writestr("manifest.ini", "name = nepaliReader\nversion = 2.2.0\n")
        self.assertIsNone(updater.checkPackage(good))
        self.assertIsNotNone(updater.checkPackage(good, expectedSize=10))  # cut short
        other = os.path.join(d, "other.nvda-addon")
        with zipfile.ZipFile(other, "w") as z:
            z.writestr("manifest.ini", "name = somethingElse\n")
        self.assertIsNotNone(updater.checkPackage(other))
        page = os.path.join(d, "page.nvda-addon")
        with open(page, "wb") as f:
            f.write(b"<html>rate limit</html>")
        self.assertIsNotNone(updater.checkPackage(page))
        self.assertIsNotNone(updater.checkPackage(os.path.join(d, "missing")))


class _FakeResponse:
    def __init__(self, data, length=None):
        self._data = data
        self._pos = 0
        self.headers = {"Content-Length": str(len(data) if length is None else length)}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        if n is None or n < 0:
            n = len(self._data) - self._pos
        chunk = self._data[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk


def _package(name="nepaliReader"):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.ini", "name = %s\nversion = 9.9.9\n" % name)
    return buf.getvalue()


class TestUpdateFlow(unittest.TestCase):
    """The whole check and download without NVDA's GUI: nothing is left waiting (a second check
    is refused only while one is running), and only a whole add-on package is installed."""

    def setUp(self):
        import urllib.request
        self._urlopen = urllib.request.urlopen
        self._launch = updater.launchInstaller
        self._current = updater.getCurrentVersion
        self._changelog = updater.fetchChangelog
        self.launched = []
        updater.launchInstaller = lambda path: self.launched.append(path)
        updater.getCurrentVersion = lambda: (2, 2, 0)
        updater.fetchChangelog = lambda tag, cur, new: ""
        updater._busy.clear()

    def tearDown(self):
        import urllib.request
        urllib.request.urlopen = self._urlopen
        updater.launchInstaller = self._launch
        updater.getCurrentVersion = self._current
        updater.fetchChangelog = self._changelog
        updater._busy.clear()

    def _wait(self):
        import threading
        import time
        t0 = time.time()
        while any(t.name == "NR_UpdateCheck" for t in threading.enumerate()) and time.time() - t0 < 10:
            time.sleep(0.01)

    def test_check_is_never_left_busy(self):
        import json
        import urllib.request
        release = {"tag_name": "v9.9.9", "body": "notes", "assets": [{"name": "nepaliReader-9.9.9.nvda-addon", "browser_download_url": "https://example.com/a.nvda-addon"}]}
        urllib.request.urlopen = lambda req, timeout=0: _FakeResponse(json.dumps(release).encode("utf-8"))
        updater.checkUpdate(manual=True)
        self._wait()
        self.assertFalse(updater._busy.is_set())
        # no network: the check ends too
        def fail(req, timeout=0):
            raise OSError("offline")
        urllib.request.urlopen = fail
        updater.checkUpdate(manual=True)
        self._wait()
        self.assertFalse(updater._busy.is_set())
        # while one runs, a second is refused (no second window or download)
        updater._busy.set()
        updater.checkUpdate(manual=True)
        self.assertFalse(any(t.name == "NR_UpdateCheck" for t in __import__("threading").enumerate()))

    def test_whole_download_is_installed(self):
        import urllib.request
        data = _package()
        urllib.request.urlopen = lambda req, timeout=0: _FakeResponse(data)
        task = updater.DownloadTask("https://example.com/a.nvda-addon", "v9.9.9")
        updater._busy.set()
        task._runDownload()
        self.assertEqual(len(self.launched), 1)
        self.assertTrue(self.launched[0].endswith("nepaliReader-9.9.9.nvda-addon"))
        self.assertIsNone(updater.checkPackage(self.launched[0]))
        self.assertFalse(updater._busy.is_set())

    def test_cut_download_is_not_installed(self):
        import os
        import urllib.request
        data = _package()
        urllib.request.urlopen = lambda req, timeout=0: _FakeResponse(data[:20], length=len(data))
        task = updater.DownloadTask("https://example.com/a.nvda-addon", "v9.9.9")
        updater._busy.set()
        task._runDownload()
        self.assertEqual(self.launched, [])
        self.assertFalse(os.path.exists(task.destPath))
        self.assertFalse(updater._busy.is_set())


if __name__ == "__main__":
    unittest.main()
