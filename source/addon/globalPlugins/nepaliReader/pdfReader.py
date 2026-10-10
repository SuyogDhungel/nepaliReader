# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - small PDF reader: objects, streams, pages and the text-drawing
# operators of page content (which glyph of which font is drawn where).
# Pure Python, no NVDA dependencies.

import re
import zlib

try:
	from . import pdfCrypt
except ImportError:
	import pdfCrypt


class PdfError(Exception):
	pass


class Name(str):
	pass


class Ref(tuple):
	__slots__ = ()

	@property
	def num(self):
		return self[0]


class Op(str):
	pass


class Stream:
	__slots__ = ("dict", "raw", "num", "gen", "_data")

	def __init__(self, d, raw, num=0, gen=0):
		self.dict = d
		self.raw = raw
		self.num = num
		self.gen = gen
		self._data = None

	def get(self, k, default=None):
		return self.dict.get(k, default)


_WS = b"\x00\t\n\x0c\r "
_TOKEN = re.compile(
	rb"(?P<ws>(?:[\x00\t\n\x0c\r ]+|%[^\r\n]*)+)"
	rb"|(?P<num>[+-]?(?:\d+\.?\d*|\.\d+))"
	rb"|(?P<name>/[^\x00\t\n\x0c\r ()<>\[\]{}/%]*)"
	rb"|(?P<str>\()"
	rb"|(?P<dopen><<)|(?P<dclose>>>)"
	rb"|(?P<hex><[0-9A-Fa-f\x00\t\n\x0c\r ]*>)"
	rb"|(?P<aopen>\[)|(?P<aclose>\])"
	rb"|(?P<kw>[^\x00\t\n\x0c\r ()<>\[\]{}/%]+)"
	rb"|(?P<bad>.)",
	re.S,
)
_NAMEESC = re.compile(rb"#([0-9A-Fa-f]{2})")
_ESC = {ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t", ord("b"): b"\b", ord("f"): b"\f", ord("("): b"(", ord(")"): b")", ord("\\"): b"\\"}


def _name(b):
	if b"#" in b:
		b = _NAMEESC.sub(lambda m: bytes([int(m.group(1), 16)]), b)
	return Name(b.decode("latin-1"))


def _literal(data, pos):
	"""pos is just after '('. Returns (bytes, new pos)."""
	out = bytearray()
	depth = 1
	n = len(data)
	i = pos
	while i < n:
		c = data[i]
		if c == 0x5C:  # backslash
			i += 1
			if i >= n:
				break
			c = data[i]
			e = _ESC.get(c)
			if e is not None:
				out += e
				i += 1
			elif 0x30 <= c <= 0x37:
				j = i
				v = 0
				while j < n and j < i + 3 and 0x30 <= data[j] <= 0x37:
					v = v * 8 + data[j] - 0x30
					j += 1
				out.append(v & 0xFF)
				i = j
			elif c == 0x0D:
				i += 1
				if i < n and data[i] == 0x0A:
					i += 1
			elif c == 0x0A:
				i += 1
			else:
				out.append(c)
				i += 1
			continue
		if c == 0x28:
			depth += 1
		elif c == 0x29:
			depth -= 1
			if depth == 0:
				return bytes(out), i + 1
		out.append(c)
		i += 1
	return bytes(out), i


def _hexstr(tok):
	h = re.sub(rb"[^0-9A-Fa-f]", b"", tok[1:-1])
	if len(h) % 2:
		h += b"0"
	return bytes.fromhex(h.decode("ascii"))


def _number(b):
	if b"." in b:
		try:
			return float(b)
		except ValueError:
			return 0.0
	try:
		return int(b)
	except ValueError:
		return 0


class _Parser:
	"""Parses PDF objects from bytes (also used for content streams)."""

	def __init__(self, data, pos=0):
		self.data = data
		self.pos = pos

	def token(self):
		m = _TOKEN.match(self.data, self.pos)
		while m and m.lastgroup == "ws":
			self.pos = m.end()
			m = _TOKEN.match(self.data, self.pos)
		if not m:
			return None, None
		self.pos = m.end()
		return m.lastgroup, m.group()

	def obj(self, content=False):
		"""Next object. In content streams, keywords come back as Op."""
		kind, tok = self.token()
		if kind is None:
			raise EOFError
		return self._value(kind, tok, content)

	def _value(self, kind, tok, content):
		if kind == "num":
			v = _number(tok)
			if not content and isinstance(v, int) and v >= 0:
				# maybe "n g R"
				save = self.pos
				k2, t2 = self.token()
				if k2 == "num" and b"." not in t2:
					k3, t3 = self.token()
					if k3 == "kw" and t3 == b"R":
						return Ref((v, int(t2)))
				self.pos = save
			return v
		if kind == "name":
			return _name(tok[1:])
		if kind == "str":
			s, self.pos = _literal(self.data, self.pos)
			return s
		if kind == "hex":
			return _hexstr(tok)
		if kind == "aopen":
			arr = []
			while True:
				k, t = self.token()
				if k is None or k == "aclose":
					return arr
				arr.append(self._value(k, t, content))
		if kind == "dopen":
			d = {}
			while True:
				k, t = self.token()
				if k is None or k == "dclose":
					return d
				if k != "name":
					continue
				key = _name(t[1:])
				k2, t2 = self.token()
				if k2 is None:
					return d
				if k2 == "dclose":
					d[key] = None
					return d
				d[key] = self._value(k2, t2, content)
		if kind == "kw":
			if tok == b"true":
				return True
			if tok == b"false":
				return False
			if tok == b"null":
				return None
			return Op(tok.decode("latin-1"))
		return Op("")


# ---------------------------------------------------------------- filters

def _flate(data):
	try:
		return zlib.decompress(data)
	except zlib.error:
		d = zlib.decompressobj()
		try:
			return d.decompress(data)
		except zlib.error:
			out = b""
			# corrupted stream: take what can be read
			for w in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
				try:
					d = zlib.decompressobj(w)
					out = d.decompress(data[:])
					if out:
						return out
				except zlib.error:
					pass
			return out


def _predict(data, parms):
	pred = int(parms.get("Predictor", 1) or 1)
	if pred < 10:
		return data
	cols = int(parms.get("Columns", 1) or 1)
	colors = int(parms.get("Colors", 1) or 1)
	bpc = int(parms.get("BitsPerComponent", 8) or 8)
	bpp = max(1, colors * bpc // 8)
	rowLen = (cols * colors * bpc + 7) // 8
	out = bytearray()
	prev = bytearray(rowLen)
	i = 0
	while i + 1 + rowLen <= len(data) + 1 and i < len(data):
		ft = data[i]
		row = bytearray(data[i + 1:i + 1 + rowLen])
		if len(row) < rowLen:
			row += bytes(rowLen - len(row))
		if ft == 1:
			for k in range(bpp, rowLen):
				row[k] = (row[k] + row[k - bpp]) & 255
		elif ft == 2:
			for k in range(rowLen):
				row[k] = (row[k] + prev[k]) & 255
		elif ft == 3:
			for k in range(rowLen):
				left = row[k - bpp] if k >= bpp else 0
				row[k] = (row[k] + ((left + prev[k]) >> 1)) & 255
		elif ft == 4:
			for k in range(rowLen):
				a = row[k - bpp] if k >= bpp else 0
				b = prev[k]
				c = prev[k - bpp] if k >= bpp else 0
				p = a + b - c
				pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
				pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
				row[k] = (row[k] + pr) & 255
		out += row
		prev = row
		i += 1 + rowLen
	return bytes(out)


def _ascii85(data):
	data = re.sub(rb"\s", b"", data)
	if data.startswith(b"<~"):
		data = data[2:]
	end = data.find(b"~>")
	if end >= 0:
		data = data[:end]
	out = bytearray()
	group = []
	for c in data:
		if c == ord("z") and not group:
			out += b"\0\0\0\0"
			continue
		if c < 33 or c > 117:
			continue
		group.append(c - 33)
		if len(group) == 5:
			v = 0
			for g in group:
				v = v * 85 + g
			out += (v & 0xFFFFFFFF).to_bytes(4, "big")
			group = []
	if group:
		n = len(group)
		group += [84] * (5 - n)
		v = 0
		for g in group:
			v = v * 85 + g
		out += (v & 0xFFFFFFFF).to_bytes(4, "big")[:n - 1]
	return bytes(out)


def _lzw(data, early=1):
	out = bytearray()
	table = [bytes([i]) for i in range(256)] + [b"", b""]
	bits = 9
	buf = 0
	nb = 0
	prev = None
	for c in data:
		buf = (buf << 8) | c
		nb += 8
		while nb >= bits:
			nb -= bits
			code = (buf >> nb) & ((1 << bits) - 1)
			if code == 256:
				table = table[:258]
				bits = 9
				prev = None
				continue
			if code == 257:
				return bytes(out)
			if prev is None:
				entry = table[code] if code < len(table) else b""
			elif code < len(table):
				entry = table[code]
				table.append(prev + entry[:1])
			else:
				entry = prev + prev[:1]
				table.append(entry)
			out += entry
			prev = entry
			if len(table) + early >= (1 << bits) and bits < 12:
				bits += 1
	return bytes(out)


def _runlength(data):
	out = bytearray()
	i = 0
	while i < len(data):
		n = data[i]
		if n == 128:
			break
		if n < 128:
			out += data[i + 1:i + 2 + n]
			i += 2 + n
		else:
			out += data[i + 1:i + 2] * (257 - n)
			i += 2
	return bytes(out)


# ---------------------------------------------------------------- document

_XREFENT = re.compile(rb"[\x00\t\n\x0c\r ]*(\d+)[ ]+(\d+)[ ]+([nf])[\x00\t\n\x0c\r ]{0,2}")


class Document:
	def __init__(self, data):
		self.data = data
		self.offsets = {}   # num -> ("n", offset) or ("s", stream num, index)
		self.trailer = {}
		self._cache = {}
		self._objstm = {}
		self.crypt = None
		try:
			self._readXrefs()
		except Exception:
			self.offsets = {}
		if not self.offsets or "Root" not in self.trailer:
			self._scan()
		enc = self.trailer.get("Encrypt")
		if enc is not None:
			encd = self.resolve(enc)
			ids = self.resolve(self.trailer.get("ID")) or [b""]
			fid = ids[0] if ids and isinstance(ids[0], bytes) else b""
			if isinstance(enc, Ref):
				self._encNum = enc[0]
			self.crypt = pdfCrypt.StandardDecryptor(encd, fid)  # ValueError if a password is needed

	# -- cross reference -----------------------------------------------------

	def _readXrefs(self):
		data = self.data
		p = data.rfind(b"startxref")
		if p < 0:
			raise PdfError("no startxref")
		m = re.match(rb"startxref\s+(\d+)", data[p:p + 40])
		off = int(m.group(1))
		seen = set()
		first = True
		while off is not None and off not in seen and 0 <= off < len(data):
			seen.add(off)
			ps = _Parser(data, off)
			kind, tok = ps.token()
			if tok == b"xref":
				trailer = self._xrefTable(ps)
			else:
				trailer = self._xrefStream(off)
			if first:
				self.trailer = dict(trailer)
				first = False
			else:
				for k, v in trailer.items():
					self.trailer.setdefault(k, v)
			x = trailer.get("XRefStm")
			if isinstance(x, int):
				try:
					self._xrefStream(x)
				except Exception:
					pass
			prev = trailer.get("Prev")
			off = prev if isinstance(prev, int) else None

	def _xrefTable(self, ps):
		data = self.data
		while True:
			kind, tok = ps.token()
			if tok == b"trailer":
				return ps.obj()
			if kind != "num":
				raise PdfError("bad xref")
			start = int(tok)
			kind, tok = ps.token()
			count = int(tok)
			pos = ps.pos
			for i in range(count):
				mm = _XREFENT.match(data, pos)
				if not mm:
					break
				if mm.group(3) == b"n":
					num = start + i
					if num not in self.offsets:
						self.offsets[num] = ("n", int(mm.group(1)))
				pos = mm.end()
			ps.pos = pos

	def _xrefStream(self, off):
		st = self._parseIndirect(off, 0, 0)[0]
		if not isinstance(st, Stream):
			raise PdfError("bad xref stream")
		d = st.dict
		data = self.decode(st, noCrypt=True)
		w = [int(x) for x in d.get("W", [1, 2, 1])]
		size = int(d.get("Size", 0) or 0)
		index = d.get("Index") or [0, size]
		rec = sum(w)
		pos = 0
		for k in range(0, len(index) - 1, 2):
			start, count = int(index[k]), int(index[k + 1])
			for i in range(count):
				if pos + rec > len(data):
					break
				f = []
				p = pos
				for wi in w:
					v = 0
					for _ in range(wi):
						v = (v << 8) | data[p]
						p += 1
					f.append(v)
				pos += rec
				t = f[0] if w[0] else 1
				num = start + i
				if num in self.offsets:
					continue
				if t == 1:
					self.offsets[num] = ("n", f[1])
				elif t == 2:
					self.offsets[num] = ("s", f[1], f[2])
		return d

	def _scan(self):
		"""Damaged cross reference: find every 'n g obj' in the file."""
		for m in re.finditer(rb"(?<![0-9])(\d+)[\x00\t\n\x0c\r ]+(\d+)[\x00\t\n\x0c\r ]+obj\b", self.data):
			self.offsets[int(m.group(1))] = ("n", m.start())
		for m in re.finditer(rb"trailer", self.data):
			try:
				t = _Parser(self.data, m.end()).obj()
				if isinstance(t, dict):
					self.trailer.update(t)
			except Exception:
				pass
		if "Root" not in self.trailer:
			# xref streams only: find the catalog
			for num in list(self.offsets):
				try:
					o = self.get(num)
				except Exception:
					continue
				if isinstance(o, Stream) and o.dict.get("Type") == "XRef":
					for k in ("Root", "Encrypt", "ID", "Info"):
						if k in o.dict and k not in self.trailer:
							self.trailer[k] = o.dict[k]
				elif isinstance(o, dict) and o.get("Type") == "Catalog":
					self.trailer.setdefault("Root", Ref((num, 0)))

	# -- objects -----------------------------------------------------------

	def _parseIndirect(self, off, num, gen):
		ps = _Parser(self.data, off)
		k1, t1 = ps.token()
		k2, t2 = ps.token()
		k3, t3 = ps.token()
		if t3 != b"obj":
			raise PdfError("not an object")
		num = int(t1)
		gen = int(t2)
		o = ps.obj()
		save = ps.pos
		k, t = ps.token()
		if t == b"stream" and isinstance(o, dict):
			p = ps.pos
			if self.data[p:p + 2] == b"\r\n":
				p += 2
			elif self.data[p:p + 1] in (b"\n", b"\r"):
				p += 1
			length = o.get("Length")
			if isinstance(length, Ref):
				try:
					length = self.get(length[0])
				except Exception:
					length = None
			end = None
			if isinstance(length, int) and length >= 0:
				e = p + length
				if self.data[e:e + 30].lstrip(b"\r\n \t").startswith(b"endstream"):
					end = e
			if end is None:
				e = self.data.find(b"endstream", p)
				end = e if e >= 0 else len(self.data)
				while end > p and self.data[end - 1:end] in (b"\n", b"\r"):
					end -= 1
			return Stream(o, self.data[p:end], num, gen), num
		ps.pos = save
		return o, num

	def get(self, num):
		if num in self._cache:
			return self._cache[num]
		ent = self.offsets.get(num)
		o = None
		if ent is not None:
			if ent[0] == "n":
				try:
					o = self._parseIndirect(ent[1], num, 0)[0]
				except Exception:
					o = None
			else:
				o = self._fromObjStm(ent[1], ent[2], num)
		self._cache[num] = o
		return o

	def _fromObjStm(self, snum, idx, num):
		tbl = self._objstm.get(snum)
		if tbl is None:
			st = self.get(snum)
			tbl = {}
			if isinstance(st, Stream):
				data = self.decode(st)
				n = int(st.dict.get("N", 0) or 0)
				first = int(st.dict.get("First", 0) or 0)
				ps = _Parser(data, 0)
				pairs = []
				for _ in range(n):
					try:
						a = ps.obj(content=True)
						b = ps.obj(content=True)
						pairs.append((int(a), int(b)))
					except Exception:
						break
				for i, (onum, ooff) in enumerate(pairs):
					try:
						tbl[onum] = _Parser(data, first + ooff).obj()
					except Exception:
						pass
			self._objstm[snum] = tbl
		return tbl.get(num)

	def resolve(self, o, depth=0):
		while isinstance(o, Ref) and depth < 20:
			o = self.get(o[0])
			depth += 1
		return o

	def decode(self, st, noCrypt=False):
		if st._data is not None:
			return st._data
		data = st.raw
		if self.crypt is not None and not noCrypt and st.dict.get("Type") != "XRef":
			try:
				data = self.crypt.decrypt(st.num, st.gen, data)
			except Exception:
				pass
		filters = self.resolve(st.dict.get("Filter"))
		parms = self.resolve(st.dict.get("DecodeParms"))
		if filters is None:
			filters = []
		elif not isinstance(filters, list):
			filters = [filters]
		if not isinstance(parms, list):
			parms = [parms] * len(filters)
		for i, f in enumerate(filters):
			p = self.resolve(parms[i]) if i < len(parms) else None
			p = p if isinstance(p, dict) else {}
			if f in ("FlateDecode", "Fl"):
				data = _predict(_flate(data), p)
			elif f in ("LZWDecode", "LZW"):
				data = _predict(_lzw(data, int(p.get("EarlyChange", 1))), p)
			elif f in ("ASCIIHexDecode", "AHx"):
				data = _hexstr(b"<" + data.split(b">")[0] + b">")
			elif f in ("ASCII85Decode", "A85"):
				data = _ascii85(data)
			elif f in ("RunLengthDecode", "RL"):
				data = _runlength(data)
			else:
				break  # images etc.: not needed
		st._data = data
		return data

	# -- pages ---------------------------------------------------------------

	def pages(self):
		root = self.resolve(self.trailer.get("Root")) or {}
		top = self.resolve(root.get("Pages"))
		out = []
		seen = set()

		def walk(node, inherited, depth):
			node = self.resolve(node)
			if not isinstance(node, dict) or depth > 40 or id(node) in seen:
				return
			seen.add(id(node))
			inh = dict(inherited)
			for k in ("Resources", "MediaBox", "CropBox", "Rotate"):
				if k in node:
					inh[k] = node[k]
			kids = self.resolve(node.get("Kids"))
			if node.get("Type") == "Pages" or (isinstance(kids, list) and node.get("Type") != "Page"):
				for k in kids or []:
					walk(k, inh, depth + 1)
			else:
				page = dict(node)
				for k, v in inh.items():
					page.setdefault(k, v)
				out.append(page)

		walk(top, {}, 0)
		return out

	def contentData(self, page):
		c = self.resolve(page.get("Contents"))
		parts = c if isinstance(c, list) else [c]
		chunks = []
		for p in parts:
			p = self.resolve(p)
			if isinstance(p, Stream):
				chunks.append(self.decode(p))
		return b"\n".join(chunks)


# ---------------------------------------------------------------- content streams

_FAST = re.compile(
	rb"[\x00\t\n\x0c\r ]*(?:"
	# drawing operators with their numbers (most of a page): skipped in one step
	rb"(?P<gfx>(?:[+-]?(?:\d+\.?\d*|\.\d+)[\x00\t\n\x0c\r ]+)*"
	rb"(?:re|m|l|c|v|y|h|f\*?|F|B\*?|b\*?|S|s|n|W\*?|w|J|j|M|i|g|G|rg|RG|k|K)(?![^\x00\t\n\x0c\r ()<>\[\]{}/%]))"
	rb"|(?P<n>[+-]?(?:\d+\.?\d*|\.\d+))(?![^\x00\t\n\x0c\r ()<>\[\]{}/%])"
	rb"|(?P<k>[^\x00\t\n\x0c\r ()<>\[\]{}/%]+)"
	rb"|(?P<nm>/[^\x00\t\n\x0c\r ()<>\[\]{}/%]*)"
	rb"|(?P<s>\((?:[^()\\]|\\.|\((?:[^()\\]|\\.|\((?:[^()\\]|\\.)*\))*\))*\))"
	rb"|(?P<h><(?!<)[0-9A-Fa-f\x00\t\n\x0c\r ]*>)"
	rb"|(?P<o>\[|<<)"
	rb"|(?P<c>\]|>>)"
	rb"|(?P<cm>%[^\r\n]*)"
	rb"|(?P<x>.))",
	re.S,
)
_EI = re.compile(rb"[\x00\t\n\x0c\r ]EI(?=[\x00\t\n\x0c\r ]|$)")


def contentOps(data):
	"""Yield (operator, operands) from a content stream. Inline images are skipped.
	Fast path: one regular expression scan; only literal strings with escapes or deeply nested
	parentheses are parsed by hand."""
	pos = 0
	n = len(data)
	operands = []
	stack = []  # open arrays / dictionaries: (kind, list, previous operands)
	while pos < n:
		restart = None
		for m in _FAST.finditer(data, pos):
			g = m.lastgroup
			if g == "gfx":
				if not stack:
					operands = []
				continue
			if g == "n":
				t = m.group(g)
				v = float(t) if b"." in t else int(t)
				operands.append(v)
			elif g == "k":
				t = m.group(g)
				if stack:
					# keyword inside an array or dictionary: true / false / null
					operands.append(True if t == b"true" else (False if t == b"false" else None))
					continue
				if t == b"BI":
					e = _EI.search(data, m.end())
					restart = e.end() if e else n
					operands = []
					break
				if t == b"true" or t == b"false":
					operands.append(t == b"true")
					continue
				if t == b"null":
					operands.append(None)
					continue
				yield t.decode("latin-1"), operands
				operands = []
			elif g == "nm":
				operands.append(_name(m.group(g)[1:]))
			elif g == "s":
				t = m.group(g)
				inner = t[1:-1]
				if b"\\" in inner or b"(" in inner:
					inner = _literal(t, 1)[0]
				operands.append(inner)
			elif g == "h":
				operands.append(_hexstr(m.group(g)))
			elif g == "o":
				stack.append((m.group(g), operands))
				operands = []
			elif g == "c":
				if stack:
					kind, prev = stack.pop()
					if kind == b"<<":
						d = {}
						it = iter(operands)
						for k in it:
							if isinstance(k, Name):
								d[k] = next(it, None)
						val = d
					else:
						val = operands
					prev.append(val)
					operands = prev
			elif g == "x":
				t = m.group(g)
				if t == b"(":
					# a string the expression could not take (deep nesting): parse by hand
					s, end = _literal(data, m.end())
					operands.append(s)
					restart = end
					break
		else:
			return
		pos = restart if restart is not None else n
