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


if __name__ == "__main__":
    unittest.main()
