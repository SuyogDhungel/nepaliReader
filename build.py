#!/usr/bin/env python3
"""Build script for Nepali Reader NVDA add-on.
Packages source/addon into nepaliReader-<version>.nvda-addon and nepaliReader-source.zip.
"""

import configparser
import os
import shutil
import sys
import zipfile

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.join(ROOT_DIR, "source", "addon")
MANIFEST_PATH = os.path.join(ADDON_DIR, "manifest.ini")


def get_version():
	config = configparser.ConfigParser()
	config.read(MANIFEST_PATH, encoding="utf-8")
	return config.get("DEFAULT", "version", fallback="1.0.0").strip()


def build_addon(version):
	out_name = f"nepaliReader-{version}.nvda-addon"
	out_path = os.path.join(ROOT_DIR, out_name)
	print(f"Building {out_name}...")

	with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
		for root, dirs, files in os.walk(ADDON_DIR):
			if "__pycache__" in root:
				continue
			for f in files:
				if f.endswith(".pyc"):
					continue
				full_path = os.path.join(root, f)
				rel_path = os.path.relpath(full_path, ADDON_DIR)
				z.write(full_path, rel_path)

	size_mb = os.path.getsize(out_path) / (1024 * 1024)
	print(f"Successfully created: {out_path} ({size_mb:.2f} MB)")
	return out_path


def build_source():
	out_name = "nepaliReader-source.zip"
	out_path = os.path.join(ROOT_DIR, out_name)
	source_dir = os.path.join(ROOT_DIR, "source")
	print(f"Building {out_name}...")

	with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
		for root, dirs, files in os.walk(source_dir):
			if "__pycache__" in root:
				continue
			for f in files:
				if f.endswith(".pyc"):
					continue
				full_path = os.path.join(root, f)
				rel_path = os.path.relpath(full_path, source_dir)
				z.write(full_path, rel_path)

	size_mb = os.path.getsize(out_path) / (1024 * 1024)
	print(f"Successfully created: {out_path} ({size_mb:.2f} MB)")
	return out_path


def main():
	version = get_version()
	print(f"Nepali Reader version: {version}")
	build_addon(version)
	build_source()


if __name__ == "__main__":
	main()
