# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - which letters each glyph of a Devanagari font shows.
#
# A PDF stores glyph numbers; its "ToUnicode" text table is often wrong for Devanagari
# (Word, InDesign, many printers). The glyph itself is right. This module knows, for many
# Devanagari fonts, the letters behind every glyph:
#   * a bundled table (glyphRefs.dat) for common fonts, built from the fonts' own cmap/GSUB;
#   * fonts installed on this computer (Windows Fonts folders), read on demand and cached.
# Glyphs are recognised by an outline fingerprint, so renumbered PDF subsets work too.
# No NVDA dependencies.

import json
import os
import re
import threading
import zlib

try:
	from . import sfnt
except ImportError:
	import sfnt

_lock = threading.Lock()
_byHash = {}      # outline hash -> text over all fonts (None when fonts disagree)
_byFamily = {}    # normalised family -> [(upm, advances, strings, {hash: text})]
_loaded = False
_cacheDir = None
_systemIndex = None  # [(normalised family+style, normalised family, path, face)]


def norm(name):
	"""'BCDFEE+Kalimati,Bold' -> 'kalimati'; 'NotoSerifDevanagari-SemiBold' -> 'notoserifdevanagari'."""
	name = name or ""
	if "+" in name[:8]:
		name = name.split("+", 1)[1]
	name = re.split(r"[,-]", name)[0]
	name = re.sub(r"(PSMT|MT|PS)$", "", name)
	return re.sub(r"[^a-z0-9]", "", name.lower())


def styleOf(name):
	n = (name or "").lower()
	for k in ("semibold", "extrabold", "bolditalic", "bold", "medium", "light", "italic", "black", "thin"):
		if k in n:
			return k
	return "regular"


def _isDeva(s):
	return any("\u0900" <= c <= "\u097f" for c in s) if s else False


def _add(table, family):
	upm, rows = table
	adv = [r[1] for r in rows]
	strs = [r[0] for r in rows]
	hm = {}
	for s, a, h in rows:
		if h and s:
			if h in hm:
				curr = hm[h]
				if not _isDeva(curr) and _isDeva(s):
					hm[h] = s
			else:
				hm[h] = s
			if h not in _byHash:
				_byHash[h] = s
			elif _byHash[h] != s:
				if not _isDeva(_byHash[h]) and _isDeva(s):
					_byHash[h] = s
				elif _isDeva(_byHash[h]) and not _isDeva(s):
					pass
				else:
					_byHash[h] = None
	_byFamily.setdefault(family, []).append((upm, adv, strs, hm))


def load(path=None, cacheDir=None):
	"""Load the bundled tables. Safe to call from a background thread."""
	global _loaded, _cacheDir
	with _lock:
		if _loaded:
			return
		if path is None:
			path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glyphRefs.dat")
		_cacheDir = cacheDir
		try:
			with open(path, "rb") as f:
				data = json.loads(zlib.decompress(f.read()).decode("utf-8"))
			for ent in data["fonts"]:
				rows = list(zip(ent["str"], ent["adv"], ent["hash"]))
				_add((ent["upm"], rows), ent["family"])
		except FileNotFoundError:
			pass
		_loaded = True


def lookupHash(h):
	return _byHash.get(h)


def familyTables(family):
	return _byFamily.get(family, [])


# ---------------------------------------------------------------- fonts on this computer

def _fontDirs():
	dirs = []
	win = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
	if win:
		dirs.append(os.path.join(win, "Fonts"))
	local = os.environ.get("LOCALAPPDATA")
	if local:
		dirs.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
	extra = os.environ.get("NEPALIREADER_FONTDIRS")
	if extra:
		dirs.extend(extra.split(os.pathsep))
	return [d for d in dirs if os.path.isdir(d)]


def _systemFonts():
	"""Names of the installed fonts (read once, cached on disk by file size and time)."""
	global _systemIndex
	if _systemIndex is not None:
		return _systemIndex
	cache = {}
	cpath = os.path.join(_cacheDir, "fontnames.json") if _cacheDir else None
	if cpath and os.path.exists(cpath):
		try:
			with open(cpath, "r", encoding="utf-8") as f:
				cache = json.load(f)
		except Exception:
			cache = {}
	out = []
	newCache = {}
	for d in _fontDirs():
		try:
			files = os.listdir(d)
		except OSError:
			continue
		for fn in files:
			if not fn.lower().endswith((".ttf", ".ttc", ".otf")):
				continue
			p = os.path.join(d, fn)
			try:
				st = os.stat(p)
			except OSError:
				continue
			key = "%s|%d|%d" % (p, st.st_size, int(st.st_mtime))
			ent = cache.get(key)
			if ent is None:
				ent = []
				try:
					data = sfnt.readTables(p, ("name", "cmap", "maxp", "head"))
					for face in range(min(sfnt.faceCount(data), 8)):
						try:
							font = sfnt.Font(data, face)
							fam, sub, full, ps = font.names()
							cm = font.cmap()
							deva = any(0x900 <= c <= 0x97F for c in cm)
							ent.append([face, fam, sub, ps, deva])
						except Exception:
							continue
				except Exception:
					ent = []
			newCache[key] = ent
			for face, fam, sub, ps, deva in ent:
				out.append((norm(fam), norm(ps), styleOf(sub + " " + ps), p, face, deva))
	if cpath:
		try:
			os.makedirs(_cacheDir, exist_ok=True)
			with open(cpath, "w", encoding="utf-8") as f:
				json.dump(newCache, f)
		except Exception:
			pass
	_systemIndex = out
	return out


_systemLoaded = set()


def loadSystemFont(baseFontName):
	"""Read the installed font with this PDF font's name (if any) into the tables. Returns True if found."""
	fam_lower = (baseFontName or "").lower()
	if any(s in fam_lower for s in ("wingdings", "webdings", "symbol", "dingbats")):
		return False
	family = norm(baseFontName)
	style = styleOf(baseFontName)
	if not family:
		return False
	with _lock:
		key = (family, style)
		if key in _systemLoaded:
			return True
		cands = [x for x in _systemFonts() if family in (x[0], x[1])]
		if not cands:
			return False
		cands.sort(key=lambda x: (x[2] != style, not x[5]))
		fam, ps, st, path, face, deva = cands[0]
		table = None
		cfile = None
		if _cacheDir:
			try:
				s = os.stat(path)
				cfile = os.path.join(_cacheDir, "ref_%s_%s_%d_%d.json" % (fam or ps, st, s.st_size, face))
				if os.path.exists(cfile):
					with open(cfile, "r", encoding="utf-8") as f:
						d = json.load(f)
					table = (d["upm"], [tuple(r) for r in d["rows"]])
			except Exception:
				table = None
		if table is None:
			try:
				with open(path, "rb") as f:
					data = f.read()
				table = sfnt.referenceTable(sfnt.Font(data, face))
				if cfile:
					os.makedirs(_cacheDir, exist_ok=True)
					with open(cfile, "w", encoding="utf-8") as f:
						json.dump({"upm": table[0], "rows": table[1]}, f)
			except Exception:
				return False
		_add(table, family)
		_systemLoaded.add(key)
		return True
