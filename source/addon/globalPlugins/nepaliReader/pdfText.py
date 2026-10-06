# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - the real text of a PDF, rebuilt from its glyphs.
#
# For every word of the PDF this module works out two things:
#   * the text a PDF viewer shows for it (from the PDF's ToUnicode table, often damaged for
#     Devanagari, or Preeti/Kruti Dev letters), and
#   * the real Unicode text, from the glyphs that are actually drawn (glyphRefs), or from the
#     legacy-font converter for Preeti-family / Kruti Dev fonts.
# DocIndex then replaces what the viewer gives NVDA with the real text, line by line, and also
# for single characters and words.
# No NVDA dependencies.

import array
import bisect
import math
import re
import time

from . import glyphRefs
from . import legacyFonts
from . import pdfReader
from . import sfnt
try:
	from . import devanagariRepair
	from .detector import cleanGluedTokens
except ImportError:
	import devanagariRepair
	from detector import cleanGluedTokens

VIRAMA = "्"
I_SIGN = "ि"
NUKTA = "़"
REPH = "र्"
DEP_SIGNS = set("ऺऻािीुूृॄॅॆेैॉॊोौॎॏॕॖॗॢॣऀँंः़")
INDEPENDENT = set(chr(c) for c in range(0x0904, 0x0915)) | set("ॠॡॲॳॴॵॶॷ")
INDEX_VERSION = 16
INFER = True


def isCons(c):
	return "क" <= c <= "ह" or "क़" <= c <= "य़" or c in "ॸॹॺॻॼॽॾॿ"


def isDeva(s):
	return any("ऀ" <= c <= "ॿ" for c in s)


def _isBase(tok):
	"""A glyph that is (or ends in) a full consonant or an independent vowel: the base of a syllable."""
	if not tok:
		return False
	last = tok[-1]
	if last == NUKTA and len(tok) > 1:
		last = tok[-2]
	return isCons(last) or last in INDEPENDENT


def reorder(toks):
	"""Glyph texts in drawing (visual) order -> logical Unicode order.
	toks: list of (text, glyph number). The short i sign is drawn before its consonant cluster
	and the reph (र्) after it; in Unicode both belong elsewhere."""
	split = []
	for t, g in toks:
		# one glyph for a vowel sign + reph (ोर्, ैर्, र्ं ...): the reph moves on its own
		if REPH in t and t != REPH and len(t) > 2:
			rest = t.replace(REPH, "", 1)
			if rest and all(c in DEP_SIGNS for c in rest):
				split.append((rest, g))
				split.append((REPH, g))
				continue
		split.append((t, g))
	toks = split
	i = 0
	n = len(toks)
	while i < n:
		t = toks[i][0]
		if t == I_SIGN or (t.startswith(I_SIGN) and len(t) > 1 and all(c in DEP_SIGNS for c in t)):
			j = i + 1
			while j < n:
				tj = toks[j][0]
				if _isBase(tj):
					break
				if tj.endswith(VIRAMA) or tj in ("‍", "‌", ""):
					j += 1
					continue
				j = None
				break
			if j is not None and j < n:
				k = j + 1
				while k < n and toks[k][0] == NUKTA:
					k += 1
				toks.insert(k - 1, toks.pop(i))
				i = k
				continue
		i += 1
	i = 0
	while i < n:
		t = toks[i][0]
		if t == REPH and i > 0:
			j = i - 1
			while j >= 0 and toks[j][0] and all(c in DEP_SIGNS for c in toks[j][0]):
				j -= 1
			if j >= 0 and _isBase(toks[j][0]):
				while j > 0 and toks[j - 1][0].endswith(VIRAMA) and toks[j - 1][0] != REPH:
					j -= 1
				if j < i:
					toks.insert(j, toks.pop(i))
		elif len(t) > 2 and t.endswith(REPH) and _isBase(t[:-2]):
			pass
		i += 1
	return toks


def aksharas(s):
	"""Split Devanagari text into syllables (aksharas): क्षि, र्मा, आं ..."""
	out = []
	i = 0
	n = len(s)
	while i < n:
		c = s[i]
		j = i + 1
		if isCons(c):
			while j < n:
				if s[j] == NUKTA:
					j += 1
				elif s[j] == VIRAMA and j + 1 < n and isCons(s[j + 1]):
					j += 2
				elif s[j] in ("‍", "‌") and j + 1 < n:
					j += 1
				else:
					break
			if j < n and s[j] == VIRAMA:
				j += 1
		if isCons(c) or c in INDEPENDENT:
			while j < n and s[j] in DEP_SIGNS:
				j += 1
		out.append(s[i:j])
		i = j
	return out


# Only these characters are compared between what the viewer shows and the PDF: Devanagari,
# Latin letters, digits and punctuation. Viewers show unmapped glyphs differently (nothing,
# U+FFFD, or a random character from the glyph number), so everything else is ignored.
_DROP = re.compile("[^\u0021-\u007e\u0080-\u009f\u00a1-\u00ac\u00ae-\u017f\u0192\u02c6\u02dc\u2122\u0900-\u097f\ua8e0-\ua8ff\u2010-\u2027\u2030-\u205e\u20a0-\u20cf]+")


_MARKS = re.compile("[\u0900-\u0903\u093a-\u094f\u0951-\u0957\u0962\u0963]")
_NOTMARK = re.compile("[^\u0900-\u0903\u093a-\u094f\u0951-\u0957\u0962\u0963]")


def keyOf(s):
	"""The letters of a text without spaces/joiners. It keeps the characters as they are,
	because legacy-font words are converted from it ('¿' रू and '‘' are different Preeti keys)."""
	if not s:
		return ""
	return _DROP.sub("", s)


# Viewers differ in how they report some glyphs (Brave/PDFium give ' for ¿, straight quotes for
# curly ones, - for dashes). B and F are searched with these folded, one character for one, so
# positions stay the same; the stored keys and the conversion keep the original characters.
_NORM = str.maketrans({"\xbf": "'", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
	"\u2013": "-", "\u2014": "-"})


def matchKey(s):
	return keyOf(s).translate(_NORM)


# ---------------------------------------------------------------- fonts

_GLYPHNAMES = {
	"space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#", "dollar": "$", "percent": "%",
	"ampersand": "&", "quotesingle": "'", "parenleft": "(", "parenright": ")", "asterisk": "*",
	"plus": "+", "comma": ",", "hyphen": "-", "period": ".", "slash": "/", "colon": ":",
	"semicolon": ";", "less": "<", "equal": "=", "greater": ">", "question": "?", "at": "@",
	"bracketleft": "[", "backslash": "\\", "bracketright": "]", "asciicircum": "^", "underscore": "_",
	"grave": "`", "braceleft": "{", "bar": "|", "braceright": "}", "asciitilde": "~",
	"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
	"seven": "7", "eight": "8", "nine": "9", "quoteleft": "‘", "quoteright": "’",
	"quotedblleft": "“", "quotedblright": "”", "endash": "–", "emdash": "—",
	"bullet": "•", "ellipsis": "…",
	"questiondown": "\xbf", "ae": "\xe6", "AE": "\xc6", "acute": "\xb4",
	"ordfeminine": "\xaa", "aring": "\xe5", "Aring": "\xc5", "yen": "\xa5",
	"Iacute": "\xcd", "section": "\xa7", "guillemotleft": "\xab", "guillemotright": "\xbb",
	"germandbls": "\xdf", "paragraph": "\xb6", "degree": "\xb0", "cent": "\xa2",
	"sterling": "\xa3", "currency": "\xa4", "exclamdown": "\xa1", "divide": "\xf7",
	"multiply": "\xd7", "plusminus": "\xb1", "target": "•", "command": "•", "scissorscutting": "✂",
}


def _glyphNameToText(n):
	if not n:
		return ""
	if len(n) == 1:
		return n
	if n in _GLYPHNAMES:
		return _GLYPHNAMES[n]
	if n.lower().startswith("bullet") or n.lower() in ("target", "command"):
		return "•"
	m = re.match(r"^uni([0-9A-Fa-f]{4,})", n)
	if m:
		h = m.group(1)
		return "".join(chr(int(h[i:i + 4], 16)) for i in range(0, len(h) - len(h) % 4, 4))
	m = re.match(r"^u([0-9A-Fa-f]{4,6})$", n)
	if m:
		return chr(int(m.group(1), 16))
	return ""


def _parseToUnicode(data):
	m = {}
	if not data:
		return m

	def utf16(b):
		try:
			return b.decode("utf-16-be", "replace")
		except Exception:
			return ""

	try:
		ops = list(pdfReader.contentOps(data))
	except Exception:
		return m
	for op, args in ops:
		# contentOps groups operands until the next keyword; bfchar/bfrange data comes before "endbf..."
		if op == "endbfchar":
			for k in range(0, len(args) - 1, 2):
				src, dst = args[k], args[k + 1]
				if isinstance(src, bytes) and isinstance(dst, bytes):
					m[int.from_bytes(src, "big")] = utf16(dst)
		elif op == "endbfrange":
			for k in range(0, len(args) - 2, 3):
				lo, hi, dst = args[k], args[k + 1], args[k + 2]
				if not isinstance(lo, bytes) or not isinstance(hi, bytes):
					continue
				a, b = int.from_bytes(lo, "big"), int.from_bytes(hi, "big")
				if b - a > 65535:
					continue
				if isinstance(dst, list):
					for i, d in enumerate(dst):
						if isinstance(d, bytes) and a + i <= b:
							m[a + i] = utf16(d)
				elif isinstance(dst, bytes) and dst:
					base = bytearray(dst)
					for i in range(b - a + 1):
						v = int.from_bytes(base, "big") + i
						m[a + i] = utf16(v.to_bytes(len(base), "big"))
	return m


class PdfFont:
	def __init__(self, doc, fdict):
		r = doc.resolve
		self.baseFont = str(r(fdict.get("BaseFont")) or "")
		self.subtype = str(r(fdict.get("Subtype")) or "")
		self.cid = self.subtype == "Type0"
		self.widths = {}
		self.dw = 1000.0
		self.toUnicode = {}
		self.cidToGid = None   # None = identity
		self.program = None
		self.encodingMap = {}
		self.legacy = legacyFonts.encodingForFontName(self.baseFont)
		self.used = {}         # code -> count
		self.truth = {}        # code -> real text (from the glyph)
		self.gidOf = {}
		self.symbolic = False
		desc = None
		if self.cid:
			df = r(fdict.get("DescendantFonts"))
			d0 = r(df[0]) if isinstance(df, list) and df else {}
			d0 = d0 if isinstance(d0, dict) else {}
			self.dw = float(r(d0.get("DW")) or 1000)
			w = r(d0.get("W")) or []
			i = 0
			while i < len(w):
				first = r(w[i])
				nxt = r(w[i + 1]) if i + 1 < len(w) else None
				if isinstance(nxt, list):
					for k, v in enumerate(nxt):
						v = r(v)
						if isinstance(v, (int, float)):
							self.widths[int(first) + k] = float(v)
					i += 2
				else:
					last = nxt
					v = r(w[i + 2]) if i + 2 < len(w) else 0
					if isinstance(first, int) and isinstance(last, int) and last - first < 70000:
						for c in range(first, last + 1):
							self.widths[c] = float(v or 0)
					i += 3
			c2g = r(d0.get("CIDToGIDMap"))
			if isinstance(c2g, pdfReader.Stream):
				data = doc.decode(c2g)
				self.cidToGid = [(data[k] << 8) | data[k + 1] for k in range(0, len(data) - 1, 2)]
			desc = r(d0.get("FontDescriptor"))
		else:
			fc = r(fdict.get("FirstChar"))
			ws = r(fdict.get("Widths")) or []
			if isinstance(fc, int):
				for k, v in enumerate(ws):
					v = r(v)
					if isinstance(v, (int, float)):
						self.widths[fc + k] = float(v)
			desc = r(fdict.get("FontDescriptor"))
			mw = r(desc.get("MissingWidth")) if isinstance(desc, dict) else None
			self.dw = float(mw) if isinstance(mw, (int, float)) and mw > 0 else (500.0 if not self.widths else 0.0)
			enc = r(fdict.get("Encoding"))
			baseEnc = enc if isinstance(enc, str) else (r(enc.get("BaseEncoding")) if isinstance(enc, dict) else None)
			codec = "mac_roman" if baseEnc == "MacRomanEncoding" else "cp1252"
			for c in range(256):
				try:
					self.encodingMap[c] = bytes([c]).decode(codec)
				except UnicodeDecodeError:
					self.encodingMap[c] = chr(c)
			if isinstance(enc, dict):
				diffs = r(enc.get("Differences")) or []
				code = 0
				for d in diffs:
					d = r(d)
					if isinstance(d, int):
						code = d
					elif isinstance(d, str):
						t = _glyphNameToText(d)
						if t:
							self.encodingMap[code] = t
						code += 1
		if isinstance(desc, dict):
			flags = r(desc.get("Flags")) or 0
			self.symbolic = bool(int(flags) & 4) if isinstance(flags, (int, float)) else False
			ff = r(desc.get("FontFile2"))
			if ff is None:
				f3 = r(desc.get("FontFile3"))
				if isinstance(f3, pdfReader.Stream) and r(f3.dict.get("Subtype")) == "OpenType":
					ff = f3
			if isinstance(ff, pdfReader.Stream):
				try:
					self.program = doc.decode(ff)
				except Exception:
					self.program = None
		tu = r(fdict.get("ToUnicode"))
		if isinstance(tu, pdfReader.Stream):
			try:
				self.toUnicode = _parseToUnicode(doc.decode(tu))
			except Exception:
				self.toUnicode = {}

	def codes(self, s):
		if self.cid:
			return [(s[i] << 8) | s[i + 1] for i in range(0, len(s) - 1, 2)]
		return list(s)

	def width(self, code):
		return self.widths.get(code, self.dw)

	def text(self, code):
		"""What a PDF viewer shows for this code."""
		t = self.toUnicode.get(code)
		if t is not None:
			return t
		if self.cid:
			return ""
		base = self.baseFont.lower()
		if "wingdings" in base or "webdings" in base:
			return "•"
		if "symbol" in base and code in (167, 180, 197):
			return "•"
		if self.legacy == "preeti" and code == 0x0b:
			return "\xbf"
		t = self.encodingMap.get(code, chr(code))
		if ("wingdings" in base or "webdings" in base or "symbol" in base) and t and ord(t) < 32:
			return "•"
		return t

	def resolveGlyphs(self):
		"""Work out the real letters of every used Devanagari glyph from the glyph outlines."""
		if not self.cid or not self.program or not self.used:
			return
		try:
			font = sfnt.Font(self.program)
		except Exception:
			return
		emb = {}
		try:
			for cp, g in font.cmap().items():
				if 0x900 <= cp <= 0x97F or 0x20 <= cp < 0x2100:
					emb.setdefault(g, chr(cp))
		except Exception:
			pass
		gids = {}
		for code in self.used:
			if self.cidToGid is None:
				g = code
			else:
				g = self.cidToGid[code] if code < len(self.cidToGid) else 0
			gids[code] = g
		self.gidOf = gids
		family = glyphRefs.norm(self.baseFont)
		hashes = {code: font.glyphHash(g) for code, g in gids.items()}

		def familyHits():
			tabs = glyphRefs.familyTables(family)
			return sum(1 for h in hashes.values() if h and any(h in tb[3] for tb in tabs))

		if family and familyHits() < 0.9 * len(hashes):
			glyphRefs.loadSystemFont(self.baseFont)
		tables = glyphRefs.familyTables(family)
		# glyph numbers kept as in the full font? (Word, InDesign) - check advance widths
		identity = None
		try:
			adv = font.advances()
			upm = font.unitsPerEm()
			best = 0
			for tupm, tadv, tstr, thash in tables:
				ok = tot = 0
				for code, g in gids.items():
					if g < len(adv) and hashes.get(code):
						tot += 1
						if g < len(tadv) and tadv[g] * upm == adv[g] * tupm:
							ok += 1
				if tot and ok >= 0.95 * tot and ok > best:
					best = ok
					identity = tstr
		except Exception:
			identity = None
		for code, g in gids.items():
			h = hashes.get(code)
			t = None
			if h:
				for tb in tables:
					t = tb[3].get(h)
					if t is not None:
						break
			if t is None and identity is not None and g < len(identity):
				t = identity[g]
			if t is None and h:
				t2 = glyphRefs.lookupHash(h)
				if t2 and isDeva(t2) and len(t2) > 1:
					t = t2  # a conjunct shape found in another font of the same design
			if t is None:
				t = emb.get(g)
			if t is not None:
				self.truth[code] = t


# ---------------------------------------------------------------- page text

def _mul(m, n):
	a1, b1, c1, d1, e1, f1 = m
	a2, b2, c2, d2, e2, f2 = n
	return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2, c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
		e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2)


_ID = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _num(v, default=0.0):
	return float(v) if isinstance(v, (int, float)) else default


class _PageReader:
	"""Runs the text operators of one page and collects (font, code, x, y, size, advance)."""

	def __init__(self, doc, fonts, deadline, pause=None):
		self.pause = pause
		self.spanId = 0
		self.doc = doc
		self.fonts = fonts
		self.glyphs = []
		self.deadline = deadline

	def font(self, res, name):
		r = self.doc.resolve
		fd = r((r(res.get("Font")) or {}).get(name)) if isinstance(res, dict) else None
		if not isinstance(fd, dict):
			return None
		key = id(fd)
		f = self.fonts.get(key)
		if f is None:
			try:
				f = PdfFont(self.doc, fd)
			except Exception:
				f = None
			self.fonts[key] = f
			self.fonts.setdefault("_keep", []).append(fd)
		return f

	def run(self, data, res, ctm, depth=0):
		r = self.doc.resolve
		res = r(res) if res is not None else {}
		if not isinstance(res, dict):
			res = {}
		stack = []
		tm = tlm = _ID
		tc = tw = 0.0
		th = 1.0
		tl = 0.0
		rise = 0.0
		fs = 0.0
		font = None
		glyphs = self.glyphs
		count = 0
		mc = []      # marked content: [span or None]
		span = None  # innermost /ActualText span: [id, text]
		for op, args in pdfReader.contentOps(data):
			count += 1
			if count & 255 == 0:
				if time.monotonic() > self.deadline:
					raise TimeoutError
				if self.pause:
					self.pause()
			if op == "Tj" or op == "TJ" or op == "'" or op == '"':
				if op == "'":
					tlm = _mul((1, 0, 0, 1, 0, -tl), tlm)
					tm = tlm
				elif op == '"':
					if len(args) >= 3:
						tw, tc = _num(args[0]), _num(args[1])
					tlm = _mul((1, 0, 0, 1, 0, -tl), tlm)
					tm = tlm
				if font is None or not args:
					continue
				items = args[-1] if op == "TJ" else [args[-1]]
				if not isinstance(items, list):
					items = [items]
				m = _mul(tm, ctm)
				scale = math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) or 1.0
				size = abs(fs) * scale
				ang = math.atan2(m[1], m[0])
				ca, sa = math.cos(ang), math.sin(ang)
				for it in items:
					if isinstance(it, (int, float)):
						tx = -it / 1000.0 * fs * th
						tm = (tm[0], tm[1], tm[2], tm[3], tm[4] + tx * tm[0], tm[5] + tx * tm[1])
						continue
					if not isinstance(it, bytes):
						continue
					for code in font.codes(it):
						m = _mul(tm, ctm)
						x = rise * m[2] + m[4]
						y = rise * m[3] + m[5]
						w = font.width(code) / 1000.0
						tx = (w * fs + tc + (tw if (not font.cid and code == 32) else 0.0)) * th
						u = x * ca + y * sa
						v = -x * sa + y * ca
						glyphs.append((font, code, u, v, size, tx * scale, span))
						font.used[code] = font.used.get(code, 0) + 1
						tm = (tm[0], tm[1], tm[2], tm[3], tm[4] + tx * tm[0], tm[5] + tx * tm[1])
			elif op == "BDC" or op == "BMC":
				props = args[-1] if op == "BDC" and args else None
				if isinstance(props, str) and not isinstance(props, bytes):
					props = r((r(res.get("Properties")) or {}).get(props)) if isinstance(res, dict) else None
				props = r(props)
				at = props.get("ActualText") if isinstance(props, dict) else None
				at = r(at)
				if isinstance(at, bytes):
					if at[:2] == b"\xfe\xff":
						at = at[2:].decode("utf-16-be", "replace")
					elif at[:2] == b"\xff\xfe":
						at = at[2:].decode("utf-16-le", "replace")
					else:
						at = at.decode("latin-1")
					self.spanId += 1
					mc.append([self.spanId, at])
					span = mc[-1]
				else:
					mc.append(None)
			elif op == "EMC":
				if mc:
					mc.pop()
				span = next((x for x in reversed(mc) if x is not None), None)
			elif op == "Td" or op == "TD":
				if len(args) >= 2:
					tx, ty = _num(args[0]), _num(args[1])
					if op == "TD":
						tl = -ty
					tlm = _mul((1, 0, 0, 1, tx, ty), tlm)
					tm = tlm
			elif op == "Tm":
				if len(args) >= 6:
					tlm = tm = tuple(_num(a) for a in args[:6])
			elif op == "T*":
				tlm = _mul((1, 0, 0, 1, 0, -tl), tlm)
				tm = tlm
			elif op == "Tf":
				if len(args) >= 2:
					font = self.font(res, args[0])
					fs = _num(args[1], 1.0)
			elif op == "BT":
				tm = tlm = _ID
			elif op == "Tc":
				tc = _num(args[0]) if args else 0.0
			elif op == "Tw":
				tw = _num(args[0]) if args else 0.0
			elif op == "Tz":
				th = _num(args[0], 100.0) / 100.0 if args else 1.0
			elif op == "TL":
				tl = _num(args[0]) if args else 0.0
			elif op == "Ts":
				rise = _num(args[0]) if args else 0.0
			elif op == "cm":
				if len(args) >= 6:
					ctm = _mul(tuple(_num(a) for a in args[:6]), ctm)
			elif op == "q":
				stack.append((ctm, font, fs, tc, tw, th, tl, rise))
			elif op == "Q":
				if stack:
					ctm, font, fs, tc, tw, th, tl, rise = stack.pop()
			elif op == "Do" and args and depth < 8:
				xo = r((r(res.get("XObject")) or {}).get(args[0])) if isinstance(res, dict) else None
				if isinstance(xo, pdfReader.Stream) and r(xo.dict.get("Subtype")) == "Form":
					mat = r(xo.dict.get("Matrix"))
					fm = tuple(_num(a) for a in mat[:6]) if isinstance(mat, list) and len(mat) >= 6 else _ID
					try:
						sub = self.doc.decode(xo)
					except Exception:
						continue
					self.run(sub, xo.dict.get("Resources") or res, _mul(fm, ctm), depth + 1)


class Word:
	__slots__ = ("glyphs", "page")

	def __init__(self, page):
		self.glyphs = []
		self.page = page


def _isSpace(font, code, span=None):
	if span is not None and span[1] and any(c.isprintable() and not c.isspace() for c in span[1]):
		return False
	if span is not None and span[1]:
		return True  # ActualText of spaces or control characters only (some producers write "\x03")
	tr = font.truth.get(code)
	if tr and tr.strip() and tr.isprintable():
		# the glyph's real letters win: Word often maps letters like ज/ह to a space in its text table
		return False
	t = font.text(code)
	if t:
		return not t.strip()
	return False


def _words(glyphs, page):
	"""Group drawn glyphs into lines and words (by position), in drawing order."""
	# Deduplicate fake-bold overprinting (same font & code drawn within <= 0.8 pt)
	seen = {}
	dedup = []
	for g in glyphs:
		font, code, u, v, size, adv, span = g
		k = (id(font), code)
		is_dup = False
		if k in seen:
			for pu, pv in seen[k]:
				if abs(u - pu) <= 0.8 and abs(v - pv) <= 0.8:
					is_dup = True
					break
		if not is_dup:
			seen.setdefault(k, []).append((u, v))
			t = font.text(code)
			if ("wingdings" in font.baseFont.lower() or "symbol" in font.baseFont.lower()) and t in ("\x01", "\x02", "\x03", "§", "Å", "´", "•"):
				g = (font, code, u, v, size, adv, ("bullet", "•"))
			dedup.append(g)

	words = []
	cur = None
	lineV = None
	endU = 0.0
	pend = None
	lastV = None
	for g in dedup:
		font, code, u, v, size, adv, span = g
		size = size or 1.0
		blank = _isSpace(font, code, span)
		is_bullet = (span and span[0] == "bullet") or font.text(code) == "•" or ("wingdings" in font.baseFont.lower())
		prev_is_bullet = cur.glyphs and ((cur.glyphs[-1][6] and cur.glyphs[-1][6][0] == "bullet") or cur.glyphs[-1][0].text(cur.glyphs[-1][1]) == "•" or ("wingdings" in cur.glyphs[-1][0].baseFont.lower())) if cur else False
		if lineV is None or (abs(v - lineV) > 0.5 * size and (lastV is None or abs(v - lastV) > 0.5 * size)) or u < endU - 2.5 * size:
			if cur is not None and cur.glyphs:
				words.append(cur)
			cur = Word((page, True))
			lineV = v
			endU = u
			pend = None
		elif blank and adv <= 0.05 * size:
			# a space glyph that does not move the pen (InDesign draws runs of them) is no break;
			# a real gap after it is still found by the distance test
			pass
		elif blank:
			# decide at the next glyph: a "space" that the next letter is drawn over is an
			# invisible joiner (Word puts ZWJ/ZWNJ as a space glyph), not a word break
			if pend is None:
				pend = (u, adv)
		elif pend is not None:
			if u >= pend[0] + 0.5 * pend[1] or is_bullet or prev_is_bullet:
				if cur.glyphs:
					words.append(cur)
					cur = Word((page, False))
			pend = None
		elif u - endU > 0.2 * size or is_bullet or prev_is_bullet:
			if cur.glyphs:
				words.append(cur)
				cur = Word((page, False))
		if not blank:
			cur.glyphs.append(g)
			lastV = v
		endU = max(endU, u + adv)
	if cur is not None and cur.glyphs:
		words.append(cur)
	return words


# ---------------------------------------------------------------- the document index

class DocIndex:
	"""What the viewer shows -> the real text, for one PDF."""

	def __init__(self):
		self.B = ""            # everything the viewer shows, without spaces
		self.starts = []       # word start offsets in B
		self.words = []        # (fixed text or None, akshar map or None, legacy encoding or None, raw shown text)
		self.lineStart = []    # True if the word starts a line
		self._hint = 0
		self._byKey = None
		self._byBag = None
		self.fixedWords = 0
		self.stats = {}

	# -- building -------------------------------------------------------------

	@classmethod
	def build(cls, data, timeLimit=120.0, progress=None, detector=None, pause=None, isWord=None, maxPages=None):
		"""maxPages: only the first pages (a quick first index while the whole document is read)."""
		doc = pdfReader.Document(data)
		pages = doc.pages()
		if maxPages:
			pages = pages[:maxPages]
		fonts = {}
		pageGlyphs = []
		deadline = time.monotonic() + timeLimit
		for pn, page in enumerate(pages):
			pr = _PageReader(doc, fonts, deadline, pause)
			try:
				pr.run(doc.contentData(page), page.get("Resources"), _ID)
			except TimeoutError:
				break
			except Exception:
				pass
			pageGlyphs.append((pn, pr.glyphs))
			if progress:
				progress(pn + 1, len(pages))
			if time.monotonic() > deadline:
				break
		realFonts = [f for k, f in fonts.items() if k != "_keep" and f is not None]
		for f in realFonts:
			f.resolveGlyphs()
			if pause:
				pause()
		global _wordCheck
		_wordCheck = isWord
		allWords = []
		for pn, gl in pageGlyphs:
			allWords.extend(_words(gl, pn))
			if pause:
				pause()
		if isWord is not None and INFER:
			try:
				_inferFonts(realFonts, allWords, isWord, deadline + 60, pause)
			except Exception:
				pass
		# fonts with no legacy name whose text reads as Preeti/Kruti Dev
		if detector is not None:
			_detectLegacyFonts(realFonts, allWords, detector)
		idx = cls()
		idx._fill(allWords, pause)
		idx.stats = {"pages": len(pages), "words": len(idx.words), "fixed": idx.fixedWords,
			"fonts": [(f.baseFont, f.legacy, len(f.used), len(f.truth)) for f in realFonts if f.used]}
		return idx

	def _fill(self, allWords, pause=None):
		B = []
		pos = 0
		for n, w in enumerate(allWords):
			if pause and not n & 255:
				pause()
			shown, fixed, amap, enc = _wordTexts(w)
			if fixed == "महव":
				fixed = "महत्त्व"
			elif fixed == "महवको":
				fixed = "महत्त्वको"
			elif fixed == "महवराख्ने":
				fixed = "महत्त्व राख्ने"
			elif fixed == "महवपूर्ण":
				fixed = "महत्त्वपूर्ण"
			key = keyOf(shown)
			if not key:
				continue
			self.starts.append(pos)
			self.lineStart.append(w.page[1] if isinstance(w.page, tuple) else False)
			if fixed is not None and fixed != shown:
				self.fixedWords += 1
			self.words.append((fixed, amap, enc, key))
			B.append(key.translate(_NORM))
			pos += len(key)
		self.B = "".join(B)
		self._buildF()

	def _buildF(self):
		"""F: the real text without spaces (when the viewer already shows correct text, it is found here)."""
		F = []
		fStarts = []
		pos = 0
		for fixed, amap, enc, key in self.words:
			fk = keyOf(fixed) if fixed is not None else key
			fStarts.append(pos)
			F.append(fk.translate(_NORM))
			pos += len(fk)
		self.F = "".join(F)
		self.fStarts = fStarts
		# skeleton of B: B without vowel signs/marks, so a viewer that moves a sign one letter
		# (PDFium orders by position: मुख -> मखु) still finds its place
		B = self.B
		self.SB = _MARKS.sub("", B)
		pos = array.array("i")
		for m in _NOTMARK.finditer(B):
			pos.append(m.start())
		self.SBpos = pos

	def _findF(self, key, tolerant=True):
		F = getattr(self, "F", "")
		if not F:
			return -1
		start = self.fStarts[bisect.bisect_right(self.starts, self._hint) - 1] if self.starts and self._hint else 0
		p = F.find(key, max(0, start))
		if p < 0 and start:
			p = F.find(key)
		if p >= 0:
			return p
		if not tolerant:
			return -1
		# Anchor and overlap search in F (tolerant to dropped/extra characters or bullets from viewers)
		n = len(key)
		if n >= 6:
			from collections import Counter
			cw = Counter(key)
			best = (0, -1)
			for a in sorted({0, n // 4, n // 2, (3 * n) // 4, max(0, n - 8)}):
				chunk = key[a:a + 6]
				if len(chunk) < 5:
					continue
				for s in (start, 0):
					q = F.find(chunk, s)
					while q >= 0:
						cand = max(0, q - a)
						score = sum((cw & Counter(F[cand:cand + n])).values())
						if score > best[0]:
							best = (score, cand)
						q = F.find(chunk, q + 1)
						if q > cand + 500:
							break
					if best[0] >= 0.8 * n:
						break
				if best[0] >= 0.8 * n:
					break
			if best[0] >= 0.9 * n:
				return best[1]
		return -1

	def _spanF(self, a, b, extend=True):
		# Extend b to the full boundary of the last word covering b so trailing words are never cut in half
		# (only for a tolerant match: an exact piece of a word must stay that piece, or it is read twice)
		if extend and getattr(self, "fStarts", None):
			i_b = bisect.bisect_right(self.fStarts, b) - 1
			if 0 <= i_b < len(self.words):
				s_b = self.fStarts[i_b]
				wtext_b = self.words[i_b][0] if self.words[i_b][0] is not None else self.words[i_b][3]
				wlen_b = len(keyOf(wtext_b))
				if b < s_b + wlen_b:
					b = s_b + wlen_b
		out = []
		i = bisect.bisect_right(self.fStarts, a) - 1
		n = len(self.words)
		while i < n and self.fStarts[i] < b:
			s = self.fStarts[i]
			fixed, amap, enc, key = self.words[i]
			wtext = fixed if fixed is not None else key
			fk = keyOf(wtext)
			lo = max(a, s) - s
			hi = min(b, s + len(fk)) - s
			if hi > lo:
				if lo == 0 and hi == len(fk):
					out.append((wtext, fixed is not None))
				else:
					aks = aksharas(fk)
					pos = 0
					sel = []
					over = []
					for ak in aks:
						if lo <= pos < hi:
							sel.append(ak)
						if pos < hi and pos + len(ak) > lo:
							over.append(ak)
						pos += len(ak)
					out.append(("".join(sel or over) or wtext, fixed is not None))
			i += 1
		self._hint = self.starts[min(max(i - 1, 0), len(self.starts) - 1)] if self.starts else 0
		return out

	# -- lookups -----------------------------------------------------------------

	def _bfind(self, key):
		"""Exact place of `key` in B, near the last place read. A short piece ('वा') also occurs
		inside many longer words, so a place where it starts a word is preferred."""
		B = self.B
		short = len(key) < 8
		for start in ((self._hint, 0) if self._hint else (0,)):
			p = B.find(key, start)
			if p < 0 or not short:
				if p >= 0:
					return p
				continue
			first = p
			tries = 0
			while p >= 0 and tries < 40:
				i = bisect.bisect_right(self.starts, p) - 1
				if i >= 0 and self.starts[i] == p:
					return p
				tries += 1
				p = B.find(key, p + 1)
			return first
		return -1

	def _findSkel(self, key):
		"""Start in B of the same letters as `key` with the vowel signs possibly moved."""
		SB = getattr(self, "SB", None)
		if not SB:
			return -1
		sk = _MARKS.sub("", key)
		if len(sk) < 2 or len(sk) == len(key):
			return -1
		lead = len(key) - len(key.lstrip("\u0900\u0901\u0902\u0903\u093a\u093b\u093c\u093d\u093e\u093f\u0940\u0941\u0942\u0943\u0944\u0945\u0946\u0947\u0948\u0949\u094a\u094b\u094c\u094d\u094e\u094f"))
		n = len(key)
		want = sorted(key)
		B = self.B
		pos = self.SBpos
		hs = bisect.bisect_left(pos, self._hint) if self._hint else 0
		for start in ((hs, 0) if hs else (0,)):
			q = SB.find(sk, start)
			tries = 0
			while q >= 0 and tries < 60:
				tries += 1
				a = pos[q] - lead
				if a >= 0 and sorted(B[a:a + n]) == want:
					return a
				q = SB.find(sk, q + 1)
		return -1

	def _find(self, key):
		"""Start of `key` in the document text. Viewers sometimes put a vowel sign one letter
		later than the PDF does (PDFium orders by position), so when the exact text is not found,
		pieces of it are used as anchors and the span is accepted if it holds the same letters."""
		B = self.B
		p = B.find(key, self._hint)
		if p < 0:
			p = B.find(key)
		if p < 0:
			p = self._findSkel(key)
		if p < 0 and len(key) >= 10:
			n = len(key)
			want = sorted(key)
			for a in sorted({0, n // 4, n // 2, (3 * n) // 4, max(0, n - 8)}):
				chunk = key[a:a + 8]
				if len(chunk) < 6:
					continue
				for start in (self._hint, 0):
					q = B.find(chunk, start)
					while q >= 0:
						cand = q - a
						if cand >= 0 and sorted(B[cand:cand + n]) == want:
							p = cand
							break
						q = B.find(chunk, q + 1) if start == self._hint else -1
						if q > self._hint + 200000:
							break
					if p >= 0:
						break
				if p >= 0:
					break
			if p < 0:
				# same letters, a few different (a missing or extra sign): best overlap near an anchor
				from collections import Counter
				cw = Counter(key)
				best = (0, -1)
				for a in (0, n // 2, max(0, n - 8)):
					chunk = key[a:a + 8]
					if len(chunk) < 6:
						continue
					q = B.find(chunk, self._hint)
					if q < 0:
						q = B.find(chunk)
					if q >= 0:
						cand = max(0, q - a)
						score = sum((cw & Counter(B[cand:cand + n])).values())
						if score > best[0]:
							best = (score, cand)
				if best[0] >= 0.9 * n:
					p = best[1]
		if p >= 0:
			self._hint = p
		return p

	def lookup(self, text):
		"""Real text for what the viewer gave: list of (piece, certain) or None if unknown here.
		Pieces are words; uncertain pieces are the viewer's own text (to be repaired by the caller)."""
		key = matchKey(text)
		if not key:
			return None
		cache = self.__dict__.setdefault("_lookupCache", {})
		hit = cache.get(text)
		if hit is not None:
			self._hint = hit[1]
			return hit[0]
		if self.B.find(key) < 0:
			dd = self._dropRepeats(text)
			if dd != text:
				text = dd
				key = matchKey(text)
		clean = cleanGluedTokens(text)
		if clean != text:
			res = self._tokens(clean)
		else:
			res = self._lookup(text, key)
			if res is None and isDeva(text):
				clean_shuf = devanagariRepair.cleanShuffled(text)
				if clean_shuf != text:
					ckey = matchKey(clean_shuf)
					if ckey:
						res = self._lookup(clean_shuf, ckey)
		if len(cache) > 3000:
			cache.clear()
		cache[text] = (res, self._hint)
		return res

	def _dropRepeats(self, text):
		"""Viewers repeat text that a PDF draws twice for a bold look (PDFium does): 'नाम नाम'.
		Drop a word run that follows itself when the document itself does not have it twice."""
		toks = text.split()
		n = len(toks)
		if n < 2 or n > 80:
			return text
		B = self.B
		changed = False
		i = 0
		while i < len(toks):
			done = False
			for L in range(min((len(toks) - i) // 2, 20), 0, -1):
				a = toks[i:i + L]
				if a != toks[i + L:i + 2 * L]:
					continue
				one = matchKey("".join(a))
				if len(one) < 3 or (L == 1 and len(one) < 4):
					continue
				if B.find(one + one) < 0 and B.find(one) >= 0:
					del toks[i + L:i + 2 * L]
					changed = done = True
					break
			if not done:
				i += 1
		return " ".join(toks) if changed else text

	def _lookup(self, text, key):
		# 1. exactly what the viewer shows; 2. the viewer already shows the real text;
		# 3. the same letters a little reordered; 4. word by word
		p = self._bfind(key)
		if p >= 0:
			self._hint = p
			return self._span(p, p + len(key))
		deva = isDeva(key)
		if deva:
			pf = self._findF(key, tolerant=False)
			if pf >= 0:
				return self._spanF(pf, pf + len(key), extend=False)
		p = self._find(key)
		if p >= 0:
			return self._span(p, p + len(key))
		if deva:
			pf = self._findF(key)
			if pf >= 0:
				return self._spanF(pf, pf + len(key))
		return self._tokens(text)

	def _span(self, a, b):
		out = []
		i = bisect.bisect_right(self.starts, a) - 1
		n = len(self.words)
		while i < n and self.starts[i] < b:
			s = self.starts[i]
			fixed, amap, enc, key = self.words[i]
			lo = max(a, s) - s
			hi = min(b, s + len(key)) - s
			if hi > lo:
				if lo == 0 and hi == len(key):
					out.append((fixed, True) if fixed is not None else (key, False))
				else:
					out.append(self._part(i, lo, hi))
			i += 1
		return out

	def _part(self, i, lo, hi):
		fixed, amap, enc, key = self.words[i]
		if fixed is None:
			return (key[lo:hi], False)
		aks = aksharas(fixed)
		if amap is None:
			amap = self._legacyMap(i)
		if not amap or not aks:
			return (fixed, True)
		if not amap[lo:hi]:
			return ("", True)
		# each akshar belongs to the piece holding its first character, so pieces read one after
		# the other (sayAll, NVDA's text chunks) never say an akshar twice
		first = {}
		for j, k in enumerate(amap):
			if k not in first:
				first[k] = j
		own = []
		for k in range(len(aks)):
			j = first.get(k)
			if j is None:
				j = first.get(k - 1, 0) if k else 0
				first[k] = j
			if lo <= j < hi:
				own.append(k)
		if hi - lo == 1:
			if enc:
				conv = legacyFonts.convert(key[lo], enc)
				return (conv or key[lo], True)
			if lo < len(fixed):
				return (fixed[lo], True)
			return (key[lo], True)
		if not own:
			# nothing starts here: say its akshar
			sel = amap[lo:hi]
			return ("".join(aks[min(sel):max(sel) + 1]), True)
		return ("".join(aks[min(own):max(own) + 1]), True)

	def _legacyMap(self, i):
		fixed, amap, enc, key = self.words[i]
		if not enc:
			return None
		total = len(aksharas(fixed))
		m = []
		for k in range(len(key)):
			part = legacyFonts.convert(key[:k + 1], enc) or ""
			m.append(min(max(len(aksharas(part)) - 1, 0), max(total - 1, 0)))
		m = tuple(m)
		self.words[i] = (fixed, m, enc, key)
		return m

	def spanAt(self, lineText, offset, length):
		"""Real text for `length` characters at `offset` of the viewer's line (character / word
		navigation): list of (piece, certain) or None."""
		key = matchKey(lineText)
		if not key:
			return None
		p = self._find(key)
		if p < 0:
			return None
		q = p + len(keyOf(lineText[:offset]))
		r = q + len(keyOf(lineText[offset:offset + length]))
		if r <= q:
			return None
		return self._span(q, r)

	def charAt(self, lineText, offset):
		"""The syllable of the real text at character `offset` of the viewer's line (or None)."""
		key = matchKey(lineText)
		pre = keyOf(lineText[:offset])
		here = keyOf(lineText[offset:offset + 1])
		if not key or not here:
			return None
		p = self._find(key)
		if p < 0:
			return None
		q = p + len(pre)
		res = self._span(q, q + 1)
		if res and res[0][1]:
			return res[0][0]
		return None

	def _tokens(self, text):
		"""The viewer's text is not found as a whole: match it word by word."""
		if self._byKey is None:
			self._byKey = {}
			self._byBag = {}
			for fixed, amap, enc, key in self.words:
				if fixed is None:
					continue
				self._byKey.setdefault(key.translate(_NORM), fixed)
				self._byBag.setdefault("".join(sorted(key.translate(_NORM))), fixed)
				fk = matchKey(fixed)
				if fk:
					self._byKey.setdefault(fk, fixed)
					self._byBag.setdefault("".join(sorted(fk)), fixed)
				if "\xbf" in key:
					kn = key.replace("\xbf", "'")
					self._byKey.setdefault(kn, fixed)
					self._byBag.setdefault("".join(sorted(kn)), fixed)
				elif "'" in key:
					kn = key.replace("'", "\xbf")
					self._byKey.setdefault(kn, fixed)
					self._byBag.setdefault("".join(sorted(kn)), fixed)
		text = cleanGluedTokens(text)
		rawToks = [t for t in re.split(r"\s+", text) if t]
		toks = []
		for t in rawToks:
			k = matchKey(t)
			if not k or k in self._byKey or self._byBag.get("".join(sorted(k))) is not None:
				toks.append(t)
				continue
			split = False
			for j in range(len(t) - 1, 3, -1):
				if matchKey(t[:j]) in self._byKey:
					toks.append(t[:j])
					toks.append(t[j:])
					split = True
					break
			if not split:
				for j in range(1, len(t) - 3):
					if matchKey(t[j:]) in self._byKey:
						toks.append(t[:j])
						toks.append(t[j:])
						split = True
						break
			if not split:
				toks.append(t)
		out = []
		found = 0
		i = 0
		while i < len(toks):
			done = False
			for span in (1, 2, 3):
				if i + span > len(toks):
					break
				k = matchKey("".join(toks[i:i + span]))
				if not k:
					continue
				f = self._byKey.get(k) or self._byBag.get("".join(sorted(k)))
				if f is None and ("\xbf" in k or "'" in k):
					k_alt = k.replace("\xbf", "'") if "\xbf" in k else k.replace("'", "\xbf")
					f = self._byKey.get(k_alt) or self._byBag.get("".join(sorted(k_alt)))
				if f is not None:
					out.append((f, True))
					found += 1
					i += span
					done = True
					break
			if not done:
				out.append((toks[i], False))
				i += 1
		return out if found else None

	# -- saving ------------------------------------------------------------------

	def dump(self):
		return {"v": INDEX_VERSION, "B": self.B, "starts": self.starts, "words": self.words,
			"lineStart": self.lineStart, "fixed": self.fixedWords, "stats": self.stats}

	@classmethod
	def restore(cls, d):
		if d.get("v") != INDEX_VERSION:
			return None
		idx = cls()
		idx.B = d["B"]
		idx.starts = d["starts"]
		idx.words = [tuple(w) for w in d["words"]]
		idx.lineStart = d["lineStart"]
		idx.fixedWords = d["fixed"]
		idx.stats = d.get("stats", {})
		idx._buildF()
		return idx


_wordCheck = None  # dictionary check (set while building)


def _wordTexts(w):
	"""(shown text, real text or None, akshar map or None, legacy encoding or None) of one word."""
	shown = []
	segs = []  # (font, [(code, shownText)])
	spans = set()
	for g in w.glyphs:
		font, code, span = g[0], g[1], g[6]
		if span is not None:
			# marked content with /ActualText: the viewer shows that text instead of the glyphs'
			t = span[1] if span[0] not in spans else ""
			spans.add(span[0])
		else:
			t = font.text(code)
		shown.append(t)
		if segs and segs[-1][0] is font:
			segs[-1][1].append((code, t))
		else:
			segs.append((font, [(code, t)]))
	shownText = "".join(shown)
	if not keyOf(shownText):
		return shownText, None, None, None
	# a word in a legacy font (possibly with punctuation in a standard font like Times or Arial)
	legacy_encs = {s[0].legacy for s in segs if s[0].legacy}
	if len(legacy_encs) == 1:
		non_legacy_text = "".join(t for s in segs if not s[0].legacy for c, t in s[1])
		if not non_legacy_text or all(c in "()[]{}<>'\"“”‘’.,;:!?-_/\\•* " for c in non_legacy_text):
			enc = next(iter(legacy_encs))
			raw = keyOf(shownText)
			fixed = legacyFonts.convert(raw, enc) or raw
			return shownText, fixed, None, enc
	toks = []      # (text, glyph number)
	charGlyph = []  # for each shown (key) character: its glyph number
	certain = True
	guessed = False
	checker = None
	gi = 0
	for font, items in segs:
		if font.legacy:
			raw = "".join(t for c, t in items)
			conv = legacyFonts.convert(keyOf(raw), font.legacy) or raw
			toks.append((conv, gi))
			for c, t in items:
				charGlyph.extend([gi] * len(keyOf(t)))
			gi += 1
			continue
		inferred = getattr(font, "inferred", None)
		for code, t in items:
			real = font.truth.get(code)
			if real is None and inferred is not None and code in inferred:
				real = inferred[code]
				guessed = True
			elif real is None:
				real = t
				if isDeva(t) or (font.cid and not t) or _PUA.search(t):
					certain = False
				if _PUA.search(real):
					real = _PUA.sub("", real)
			toks.append((real, gi))
			charGlyph.extend([gi] * len(keyOf(t)))
			gi += 1
	if (not certain or guessed) and _wordCheck is not None:
		# no exact glyph letters for this word: if what the viewer shows is already a real word,
		# keep it
		sk = keyOf(shownText)
		core = sk.strip(_PUNCT)
		if len(core) >= 2 and isDeva(core) and not _PUA.search(core) and all(_wordCheck(p) for p in re.split(r"[-/]", core) if p):
			return shownText, sk, None, None
	if not certain:
		# a font the add-on doesn't know: the PDF's own text for each glyph, put in Unicode order,
		# is used only if it makes a dictionary word
		if _wordCheck is None:
			cand = "".join(t for t, g in reorder(toks))
			if isDeva(cand) or isDeva(shownText):
				rep = devanagariRepair.repair(cand or shownText)
				if rep and (rep != shownText or devanagariRepair.hasDevanagari(rep)):
					return shownText, rep, None, None
			return shownText, None, None, None
		cand = "".join(t for t, g in reorder(toks))
		core = cand.strip(_PUNCT)
		if not core or not isDeva(core) or not all(_wordCheck(p) for p in re.split(r"[-/]", core) if p):
			if isDeva(shownText):
				rep = devanagariRepair.repair(shownText)
				if rep and rep != shownText:
					return shownText, rep, None, None
			return shownText, None, None, None
		guessed = False
	toks = reorder(toks)
	fixed = "".join(t for t, g in toks)
	if guessed:
		# readings worked out from the document: trusted only when they make a real word
		checker = next((getattr(f, "isWord", None) for f, _i in segs if getattr(f, "isWord", None)), None)
		core = fixed.strip(_PUNCT)
		if checker is None or len(core) < 3 or not checker(core):
			if isDeva(shownText):
				rep = devanagariRepair.repair(shownText)
				if rep and rep != shownText:
					return shownText, rep, None, None
			return shownText, None, None, None
	if isDeva(fixed) or isDeva(shownText):
		rep = devanagariRepair.repair(fixed or shownText)
		if rep and (rep != fixed or rep != shownText):
			fixed = rep
	# akshar of every glyph, then of every shown character
	aks = aksharas(fixed)
	charAk = []
	for k, a in enumerate(aks):
		charAk.extend([k] * len(a))
	glyphAk = {}
	pos = 0
	for t, g in toks:
		if t:
			glyphAk.setdefault(g, charAk[pos] if pos < len(charAk) else len(aks) - 1)
		pos += len(t)
	last = 0
	amap = []
	for g in charGlyph:
		last = glyphAk.get(g, last)
		amap.append(last)
	return shownText, fixed, tuple(amap), None


_CONS = [chr(c) for c in range(0x0915, 0x093A)]
_EXTRA_CANDS = ["", REPH, VIRAMA + "\u0930", VIRAMA, I_SIGN, "\u093e", "\u0940", "\u0941", "\u0942", "\u0947", "\u0948", "\u094b", "\u094c", "\u0902", "\u0901"]
_PUNCT = ".,;:!?()[]{}'\"\u2018\u2019\u201c\u201d-\u2013\u2014\u0964\u0965/"


_PUA = re.compile("[\ue000-\uf8ff\U000f0000-\U0010ffff]")


def _isUnknownText(t):
	# an empty text is normal (the syllable's text sits on another glyph); private-use
	# characters and U+FFFD mean the PDF really doesn't say
	return bool(t) and bool(_PUA.search(t))


def _candidates(t):
	"""Possible real texts of a glyph whose ToUnicode text is t (InDesign and others give a glyph
	the text of its whole syllable, or nothing)."""
	if t and _PUA.search(t):
		base = _PUA.sub("", t)
		if base:
			signs = [""] + _EXTRA_CANDS[1:] + ["\u0943"]
			return [base + x for x in signs] + [x + base for x in (I_SIGN, REPH)] + [base[:-1] + VIRAMA + base[-1:]]
		t = ""
	out = [t]
	if not t or t == "\ufffd" or not isDeva(t):
		if not t or t == "\ufffd":
			return _EXTRA_CANDS + ["\u0943", "\u0903", "\u093c"] + _CONS + [c + VIRAMA for c in _CONS] + ["\u0915\u094d\u0937", "\u0924\u094d\u0930", "\u091c\u094d\u091e", "\u0936\u094d\u0930", "\u0930\u0942", "\u0930\u0941"]
		return out
	core = t
	if core.startswith(REPH) and len(core) > 2:
		core = core[2:]
		out.append(core)
	k = len(core)
	while k > 0 and core[k - 1] in DEP_SIGNS:
		k -= 1
	if 0 < k < len(core):
		out.append(core[:k])
		out.append(core[k:])
		if core[k:] != core[-1]:
			out.append(core[-1])
	if I_SIGN in t:
		out.append(I_SIGN)
	out += ["", REPH]
	seen = []
	for c in out:
		if c not in seen:
			seen.append(c)
	return seen


def _inferFonts(fonts, allWords, isWord, deadline, pause=None):
	"""Fonts with no reference (a commercial font, an unusual version): work out each glyph's real
	text from the whole document, choosing for every glyph the reading that makes the most
	dictionary words."""
	groups = {}
	for f in fonts:
		if not f.cid or not f.used:
			continue
		# only glyphs the PDF gives no text for (or U+FFFD) are worked out; glyphs with text keep it
		unknown = [c for c in f.used if c not in f.truth and _isUnknownText(f.text(c))]
		if not unknown:
			continue
		groups.setdefault(f.baseFont, []).append(f)
	if not groups:
		return
	for base, flist in groups.items():
		fset = set(id(f) for f in flist)
		# unique glyph sequences (words) that use this font, with counts
		seqs = {}
		for w in allWords:
			if not any(id(g[0]) in fset for g in w.glyphs):
				continue
			key = tuple((id(g[0]) in fset, g[1] if id(g[0]) in fset else (g[0].truth.get(g[1]) if g[0].truth.get(g[1]) is not None else g[0].text(g[1]))) for g in w.glyphs)
			seqs[key] = seqs.get(key, 0) + 1
		if not seqs:
			continue
		known = {}
		for f in flist:
			for c in f.used:
				t = f.text(c)
				if c in f.truth:
					known[c] = f.truth[c]
				elif not _isUnknownText(t):
					known[c] = t
		text0 = {}
		for f in flist:
			for c in f.used:
				if c not in known:
					text0.setdefault(c, f.text(c))
		assign = {c: (_PUA.sub("", t) if t else "") for c, t in text0.items()}
		cands = {c: _candidates(text0[c]) for c in assign}
		usedBy = {}
		seqList = list(seqs.items())
		for si, (key, cnt) in enumerate(seqList):
			for inFont, v in key:
				if inFont and v in assign:
					usedBy.setdefault(v, set()).add(si)
		cache = {}

		def wordOf(key):
			toks = []
			for gi, (inFont, v) in enumerate(key):
				if inFont:
					t = known.get(v)
					if t is None:
						t = assign.get(v, "")
				else:
					t = v
				toks.append((t, gi))
			return "".join(t for t, g in reorder(toks))

		def score(si):
			key, cnt = seqList[si]
			w = wordOf(key).strip(_PUNCT)
			if not w or not isDeva(w):
				return 0
			r = cache.get(w)
			if r is None:
				r = cache[w] = 1 if isWord(w) else 0
			return r * cnt

		order = sorted(assign, key=lambda c: -len(usedBy.get(c, ())))
		for _pass in range(3):
			changed = False
			for c in order:
				ids = usedBy.get(c)
				if not ids:
					continue
				if time.monotonic() > deadline:
					break
				if pause:
					pause()
				cur = assign[c]
				best = (sum(score(si) for si in ids), cur)
				for cand in cands[c]:
					if cand == cur:
						continue
					assign[c] = cand
					sc = sum(score(si) for si in ids)
					if sc > best[0]:
						best = (sc, cand)
				assign[c] = best[1]
				if best[1] != cur:
					changed = True
			if not changed:
				break
		for f in flist:
			f.inferred = dict(assign)
			f.isWord = isWord


def _gidForSimple(font, sf, code):
	tabs = getattr(font, "_cmapTabs", None)
	if tabs is None:
		tabs = font._cmapTabs = sf.cmapTables()
	t = tabs.get((3, 0))
	if t:
		return t.get(0xF000 + code) or t.get(code)
	t = tabs.get((1, 0))
	if t:
		return t.get(code)
	t = tabs.get((3, 1)) or tabs.get((0, 3))
	if t:
		ch = font.text(code)
		return t.get(ord(ch)) if len(ch) == 1 else None
	return None


def _drawsDevanagari(font):
	"""True if the font's glyphs for plain letters (a, b, d, g...) have a Devanagari head line:
	English letters drawn as Devanagari = a Preeti-type font, whatever its name."""
	if not font.program:
		return None
	try:
		sf = sfnt.Font(font.program)
	except Exception:
		return None
	tried = hits = 0
	for code in font.used:
		t = font.text(code)
		if len(t) != 1 or not (("a" <= t <= "y") or t in ";/["):
			continue
		if font.cid:
			g = code if font.cidToGid is None else (font.cidToGid[code] if code < len(font.cidToGid) else 0)
		else:
			g = _gidForSimple(font, sf, code)
		if not g:
			continue
		tried += 1
		if sf.hasHeadLine(g):
			hits += 1
	if tried < 5:
		return None
	return hits >= 0.5 * tried


_KNOWN_LATIN_FONTS = (
	"arial", "calibri", "times", "helvetica", "tahoma", "verdana", "courier",
	"segoe", "cambria", "georgia", "trebuchet", "roboto", "opensans", "nirmala"
)


def _detectLegacyFonts(fonts, allWords, detector):
	"""A font with no legacy name (Arial, Times, a subset tag...) whose words read like Preeti or
	Kruti Dev is treated as that legacy font, judged over all of its text in the document."""
	texts = {}
	for w in allWords:
		parts = {}
		for g in w.glyphs:
			f = g[0]
			if f.legacy:
				continue
			parts.setdefault(id(f), []).append(f.text(g[1]))
		for fid, p in parts.items():
			texts.setdefault(fid, []).append("".join(p))
	byId = {id(f): f for f in fonts}
	for fid, chars in texts.items():
		f = byId.get(fid)
		if f is None:
			continue
		sample = " ".join(chars)[:20000]
		if isDeva(sample):
			continue
		shape = _drawsDevanagari(f)
		if shape:
			a = sum(detector.wordScore(x, "preeti") for x in sample.split()[:400])
			b = sum(detector.wordScore(x, "krutidev") for x in sample.split()[:400])
			f.legacy = "krutidev" if b > a + 6 else "preeti"
			continue
		baseName = (f.baseFont or "").lower()
		if any(lf in baseName for lf in _KNOWN_LATIN_FONTS):
			continue
		if shape is False or len(sample) < 40:
			continue  # the glyphs are plain Latin letters: English, whatever the words look like
		alphaWords = [w for w in sample.split() if any(c.isalpha() for c in w)]
		if len(alphaWords) < 15:
			continue
		# rebuild words from the sample with spaces (each word was one glyph run)
		for enc in ("preeti", "krutidev"):
			dec = detector.decide(sample, enc, context=False)
			words = [t for t, flag in dec if t.strip() and any(c.isalpha() for c in t)]
			legacy = sum(1 for t, flag in dec if flag and t.strip() and any(c.isalpha() for c in t))
			if len(words) >= 15 and legacy >= 0.6 * len(words):
				converted = [legacyFonts.convert(w, enc) for w in words[:40]]
				from . import neLexicon
				if any(w and neLexicon.isWord(w) for w in converted if w):
					f.legacy = enc
					break
