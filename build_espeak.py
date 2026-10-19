#!/usr/bin/env python3
"""Build script for the Nepali eSpeak NVDA add-on: the synthesizer (source/espeak) with the
Nepali Reader built in (source/addon/globalPlugins/nepaliReader, packaged as
globalPlugins/nepaliEspeakReader, which makes it run always on, in PDFs and Word only).
Writes nepaliEspeak-<version>.nvda-addon."""

import os
import zipfile

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ESPEAK_DIR = os.path.join(ROOT_DIR, "source", "espeak")
READER_DIR = os.path.join(ROOT_DIR, "source", "addon", "globalPlugins", "nepaliReader")
READER_PACKAGE = "globalPlugins/nepaliEspeakReader"


def get_version():
	with open(os.path.join(ESPEAK_DIR, "manifest.ini"), "r", encoding="utf-8") as f:
		for line in f:
			if line.startswith("version"):
				return line.split("=", 1)[1].strip().strip('"').strip("'")
	return "1.0.0"


def files(base):
	for root, dirs, names in os.walk(base):
		dirs[:] = [d for d in dirs if d != "__pycache__"]
		for n in names:
			if n.endswith(".pyc"):
				continue
			full = os.path.join(root, n)
			yield full, os.path.relpath(full, base).replace(os.sep, "/")


def main():
	version = get_version()
	out_path = os.path.join(ROOT_DIR, "nepaliEspeak-%s.nvda-addon" % version)
	print("Building %s..." % os.path.basename(out_path))
	with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
		for full, rel in files(ESPEAK_DIR):
			z.write(full, rel)
		for full, rel in files(READER_DIR):
			z.write(full, READER_PACKAGE + "/" + rel)
	print("Successfully created: %s (%.2f MB)" % (out_path, os.path.getsize(out_path) / (1024 * 1024)))


if __name__ == "__main__":
	main()
