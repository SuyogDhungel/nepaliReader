# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - a small diagnostic log (nepaliReader\diag.log in NVDA's settings
# folder), so problems on a user's computer can be seen: which window, what NVDA read, what the
# add-on changed it to, and any error. Kept small (rotates at 400 KB).
# Lines are collected in memory and written by a background thread about once a second: opening
# the file for every line read (a virus scanner looks at it each time) slowed NVDA down.

import os
import threading
import time
import traceback

_path = None
_lock = threading.Lock()
_pending = []
_wake = threading.Event()
_stopNow = threading.Event()
_writer = None
_stopping = [False]
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


def _run():
	global _writer
	me = threading.current_thread()
	while True:
		woke = _wake.wait(3.0)
		if woke and not _stopping[0]:
			# collect a second's lines into one write (switching off ends the wait at once)
			_stopNow.wait(1.0)
		_wake.clear()
		flush()
		with _lock:
			if _stopping[0] or (not woke and not _pending):
				# nothing more to write (or Nepali mode is off): the thread ends
				if _writer is me:
					_writer = None
				return


def stop():
	"""Write what is left and end the writing thread (Nepali mode switched off, NVDA exits)."""
	global _writer
	with _lock:
		w = _writer
		_stopping[0] = True
	_stopNow.set()
	_wake.set()
	if w is not None and w is not threading.current_thread():
		w.join(1.0)
	flush()
	with _lock:
		_stopping[0] = False
	_stopNow.clear()


def flush():
	"""Write the collected lines now."""
	with _lock:
		lines = _pending[:]
		del _pending[:]
		path = _path
	if not lines or path is None:
		return
	try:
		with open(path, "a", encoding="utf-8") as f:
			f.write("".join(lines))
	except Exception:
		pass


def _add(text):
	global _writer
	with _lock:
		_pending.append(text)
		if len(_pending) > 5000:
			del _pending[:1000]
		if _writer is None and not _stopping[0]:
			_writer = threading.Thread(target=_run, name="NepaliReaderDiag", daemon=True)
			_writer.start()
	_wake.set()


def write(msg):
	global _count
	if _path is None:
		return
	_count += 1
	_add("%s %s\n" % (time.strftime("%H:%M:%S"), msg))


def exception(msg):
	if _path is None:
		return
	_add("%s ERROR %s\n%s\n" % (time.strftime("%H:%M:%S"), msg, traceback.format_exc()))
