# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - finds the PDF file that is open in the focused window, so the add-on
# can read the file itself. Works with Chrome/Edge/Firefox (from the document address), and with
# Adobe Reader, Foxit, SumatraPDF and others (from the window title, the program's command line,
# Windows' recent files and the usual folders).

import ctypes
import os
import re
import tempfile
import threading
import urllib.parse

from logHandler import log

_PDF_TITLE = re.compile(r"([^\\/:*?\"<>|]+?\.pdf)\b", re.I)


def _isPdfUrl(u):
	if not u:
		return False
	low = u.lower()
	return (
		".pdf" in low
		or "mhjfbmdgcfjbbpaeojofohoefgiehjai" in low
		or "application/pdf" in low
		or "/pdf" in low
		or "type=pdf" in low
		or "=pdf" in low
	)


def _urlFromObject(obj):
	"""The address of the document (Chrome, Edge, Firefox), walking up from obj."""
	seen = 0
	# browse mode: the tree interceptor knows the document address directly
	try:
		ident = getattr(obj, "documentConstantIdentifier", None)
		if ident and _isPdfUrl(ident):
			return ident
	except Exception:
		pass
	o = getattr(obj, "rootNVDAObject", None) or obj
	while o is not None and seen < 40:
		seen += 1
		try:
			ti = getattr(o, "treeInterceptor", None)
			ident = getattr(ti, "documentConstantIdentifier", None) if ti else None
			if ident and _isPdfUrl(ident):
				return ident
		except Exception:
			pass
		try:
			ia = getattr(o, "IAccessibleObject", None)
			if ia is not None:
				v = ia.accValue(getattr(o, "IAccessibleChildID", 0))
				if v and _isPdfUrl(v):
					return v
		except Exception:
			pass
		try:
			o = o.parent
		except Exception:
			break
	return None


def _pathFromUrl(url):
	if not url:
		return None
	u = url.strip()
	if u.startswith("chrome-extension:") or "src=" in u:
		m = re.search(r"[?&]src=([^&]+)", u)
		if m:
			u = urllib.parse.unquote(m.group(1))
	if u.lower().startswith("file:"):
		p = urllib.parse.unquote(urllib.parse.urlparse(u).path)
		if re.match(r"^/[A-Za-z]:", p):
			p = p[1:]
		host = urllib.parse.urlparse(u).netloc
		if host and host != "localhost":
			p = "\\\\" + host + p.replace("/", "\\")
		return os.path.normpath(p)
	if u.lower().startswith(("http://", "https://")):
		return u
	return None


def _commandLine(pid):
	"""Command line of another process (Windows 8.1 and later)."""
	try:
		k32 = ctypes.windll.kernel32
		ntdll = ctypes.windll.ntdll
		h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
		if not h:
			return ""
		try:
			size = ctypes.c_ulong(0)
			buf = ctypes.create_string_buffer(65536)
			st = ntdll.NtQueryInformationProcess(h, 60, buf, len(buf), ctypes.byref(size))
			if st != 0:
				return ""

			class UNICODE_STRING(ctypes.Structure):
				_fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort), ("Buffer", ctypes.c_void_p)]

			us = UNICODE_STRING.from_buffer(buf)
			return ctypes.wstring_at(us.Buffer, us.Length // 2) if us.Buffer else ""
		finally:
			k32.CloseHandle(h)
	except Exception:
		return ""


def _recentLink(name):
	appdata = os.environ.get("APPDATA")
	if not appdata:
		return None
	lnk = os.path.join(appdata, "Microsoft", "Windows", "Recent", name + ".lnk")
	if not os.path.exists(lnk):
		return None
	try:
		import comtypes.client
		sh = comtypes.client.CreateObject("WScript.Shell", dynamic=True)
		target = sh.CreateShortcut(lnk).TargetPath
		if target and os.path.isfile(target):
			return target
	except Exception:
		log.debugWarning("Nepali Reader: could not read recent link", exc_info=True)
	return None


def _adobeRecent(name):
	try:
		import winreg
	except ImportError:
		return None
	for prod in ("Adobe Acrobat", "Acrobat Reader"):
		for ver in ("DC", "2020", "2017", "11.0"):
			base = r"Software\Adobe\%s\%s\AVGeneral\cRecentFiles" % (prod, ver)
			try:
				k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base)
			except OSError:
				continue
			try:
				for i in range(30):
					try:
						sub = winreg.OpenKey(k, "c%d" % (i + 1))
						val, _t = winreg.QueryValueEx(sub, "tDIText")
					except OSError:
						continue
					if isinstance(val, bytes):
						val = val.decode("latin-1", "ignore")
					p = val.strip("\x00")
					if p.startswith("/"):
						p = p[1:]
						p = p[0] + ":" + p[1:] if len(p) > 1 and p[1] == "/" else p
					p = os.path.normpath(p.replace("/", "\\"))
					if os.path.basename(p).lower() == name.lower() and os.path.isfile(p):
						return p
			finally:
				winreg.CloseKey(k)
	return None


def _searchFolders(name, limit=40000):
	home = os.path.expanduser("~")
	roots = [os.path.join(home, d) for d in ("Downloads", "Desktop", "Documents", "OneDrive")]
	seen = 0
	lname = name.lower()
	for root in roots:
		if not os.path.isdir(root):
			continue
		for dirpath, dirnames, filenames in os.walk(root):
			seen += len(filenames) + len(dirnames)
			if dirpath[len(root):].count(os.sep) >= 4:
				dirnames[:] = []
			dirnames[:] = [d for d in dirnames if not d.startswith((".", "$")) and d.lower() not in ("node_modules", "appdata")]
			for fn in filenames:
				if fn.lower() == lname:
					return os.path.join(dirpath, fn)
			if seen > limit:
				break
	return None


def _findRecentPdfByTitle(title):
	"""Tries to find a recent PDF file matching a window title that doesn't end in .pdf."""
	if not title:
		return None
	clean = re.sub(
		r"\s*-\s*(Google Chrome|Microsoft\s*Edge|Mozilla Firefox|Chrome|Edge|Firefox|Adobe Acrobat|Acrobat Reader|Adobe|SumatraPDF|Foxit).*$",
		"", title, flags=re.I
	).strip()
	if not clean or len(clean) < 3:
		return None

	home = os.path.expanduser("~")
	roots = [os.path.join(home, d) for d in ("Downloads", "Desktop", "Documents")]
	candidates = []
	for r in roots:
		if not os.path.isdir(r):
			continue
		try:
			for fn in os.listdir(r):
				if fn.lower().endswith(".pdf"):
					full = os.path.join(r, fn)
					try:
						candidates.append((os.path.getmtime(full), full))
					except OSError:
						pass
		except OSError:
			pass
	candidates.sort(reverse=True)

	# 1. Match title byte substring in recent PDFs (first 5MB)
	raw_b = clean.encode("latin-1", "ignore")[:25]
	if len(raw_b) >= 4:
		for _mtime, p in candidates[:20]:
			try:
				with open(p, "rb") as f:
					if raw_b in f.read(5 * 1024 * 1024):
						return p
			except Exception:
				pass

	# 2. Match Unicode converted title words in filename
	try:
		from . import legacyFonts
		conv = legacyFonts.convert(clean, "preeti") or ""
		words = [w for w in re.split(r"[\s\-_\.,]+", conv) if len(w) >= 3]
		if words:
			for _mtime, p in candidates[:20]:
				bn = os.path.basename(p)
				if any(w in bn for w in words):
					return p
	except Exception:
		pass

	# 3. Match clean words in filename (require specific non-generic words to match)
	_GENERIC = {"nepal", "nepali", "news", "bank", "page", "home", "document", "report", "file", "download", "view", "post", "dashboard", "online", "login", "portal", "untitled", "member"}
	clean_words = [w.lower() for w in re.split(r"[\s\-_\.,]+", clean) if len(w) >= 4]
	specific = [w for w in clean_words if w not in _GENERIC]
	if specific:
		for _mtime, p in candidates[:20]:
			bn = os.path.basename(p).lower()
			if sum(1 for w in specific if w in bn) >= max(1, (len(specific) + 1) // 2):
				return p
	elif len(clean_words) >= 3:
		for _mtime, p in candidates[:20]:
			bn = os.path.basename(p).lower()
			if sum(1 for w in clean_words if w in bn) >= 2:
				return p

	return None


def findFromTitle(title, pid=None):
	"""The PDF file of a viewer window, from its title and its program (no NVDA objects needed,
	so this can run in a background thread). Returns a local path or None."""
	m = _PDF_TITLE.search(title or "")
	name = m.group(1).strip() if m else None
	if pid:
		cl = _commandLine(pid)
		for cand in re.findall(r'"([^"]+\.pdf)"|(\S+\.pdf)', cl, re.I):
			c = cand[0] or cand[1]
			if os.path.isfile(c) and (not name or os.path.basename(c).lower() == name.lower()):
				return c
	if name:
		for fn in (_recentLink, _adobeRecent, _searchFolders):
			try:
				r = fn(name)
			except Exception:
				r = None
			if r:
				return r
	# If no .pdf in title (e.g. Chrome displaying PDF metadata title):
	return _findRecentPdfByTitle(title)


_dlLock = threading.Lock()


def readPdf(location, maxBytes=200 * 1024 * 1024):
	"""The file's bytes (downloading web PDFs once into the temp folder)."""
	if location.startswith(("http://", "https://")):
		import hashlib
		import ssl
		import urllib.request
		import urllib.error
		fn = os.path.join(tempfile.gettempdir(), "nepaliReader_%s.pdf" % hashlib.md5(location.encode("utf-8")).hexdigest()[:16])
		with _dlLock:
			if not os.path.exists(fn):
				headers = {
					"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 NVDA-NepaliReader",
					"Accept": "application/pdf,*/*",
				}
				req = urllib.request.Request(location, headers=headers)
				data = None
				try:
					ctx = ssl.create_default_context()
					with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
						data = r.read(maxBytes + 1)
				except (ssl.SSLError, urllib.error.URLError):
					try:
						ctx_unverified = ssl._create_unverified_context()
						ctx_unverified.check_hostname = False
						with urllib.request.urlopen(req, timeout=30, context=ctx_unverified) as r:
							data = r.read(maxBytes + 1)
					except Exception:
						data = None
				except Exception:
					data = None
				if not data or (not data.startswith(b"%PDF") and b"%PDF" not in data[:1024]):
					return None
				with open(fn, "wb") as f:
					f.write(data)
		location = fn
	if not os.path.isfile(location) or os.path.getsize(location) > maxBytes:
		return None
	with open(location, "rb") as f:
		return f.read()
