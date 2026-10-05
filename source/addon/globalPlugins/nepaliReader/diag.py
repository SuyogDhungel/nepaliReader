# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - a small diagnostic log (nepaliReader\diag.log in NVDA's settings
# folder), so problems on a user's computer can be seen: which window, what NVDA read, what the
# add-on changed it to, and any error. Kept small (rotates at 400 KB).

import os
import threading
import time
import traceback

_path = None
_lock = threading.Lock()
_count = 0
MAX_READS = 2000


def start(folder):
	global _path
	try:
		os.makedirs(folder, exist_ok=True)
		_path = os.path.join(folder, "diag.log")
		if os.path.exists(_path) and os.path.getsize(_path) > 400 * 1024:
			os.replace(_path, _path + ".old")
		write("---- NVDA started, Nepali Reader %s" % _version())
	except Exception:
		_path = None


def _version():
	try:
		import addonHandler
		a = addonHandler.getCodeAddon()
		return a.manifest["version"]
	except Exception:
		return "?"


def wanted():
	"""Log readings of every NVDA session."""
	return _path is not None and _count < MAX_READS


def write(msg):
	global _count
	if _path is None:
		return
	with _lock:
		_count += 1
		try:
			with open(_path, "a", encoding="utf-8") as f:
				f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
		except Exception:
			pass


def exception(msg):
	if _path is None:
		return
	with _lock:
		try:
			with open(_path, "a", encoding="utf-8") as f:
				f.write("%s ERROR %s\n%s\n" % (time.strftime("%H:%M:%S"), msg, traceback.format_exc()))
		except Exception:
			pass
