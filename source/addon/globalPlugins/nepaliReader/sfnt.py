# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - small TrueType/OpenType reader.
# Reads what is needed to find the real letters behind each glyph of a font:
# glyph outlines (to recognise the same glyph inside a PDF), the cmap, advance widths and
# the GSUB tables (which say which letters form each conjunct, half form, reph...).
# Pure Python, no NVDA dependencies.

import hashlib
import struct

VIRAMA = "्"


class FontError(Exception):
	pass


def _u16(b, o):
	return (b[o] << 8) | b[o + 1]


def _s16(b, o):
	v = (b[o] << 8) | b[o + 1]
	return v - 65536 if v >= 32768 else v


def _u32(b, o):
	return struct.unpack_from(">I", b, o)[0]


class Font:
	"""One font (a TrueType file, or one face of a .ttc collection)."""

	def __init__(self, data, faceIndex=0):
		self.data = data = bytes(data)
		off = 0
		if data[:4] == b"ttcf":
			n = _u32(data, 8)
			if faceIndex >= n:
				raise FontError("no such face")
			off = _u32(data, 12 + 4 * faceIndex)
		self.tables = {}
		try:
			numTables = _u16(data, off + 4)
			for i in range(numTables):
				rec = off + 12 + 16 * i
				tag = data[rec:rec + 4].decode("latin-1")
				self.tables[tag] = (_u32(data, rec + 8), _u32(data, rec + 12))
		except Exception:
			raise FontError("bad font directory")
		if "maxp" not in self.tables:
			raise FontError("no maxp")
		self.numGlyphs = _u16(data, self.tables["maxp"][0] + 4)
		self._loca = None
		self._hashes = {}

	def table(self, tag):
		t = self.tables.get(tag)
		if not t:
			return None
		o, n = t
		return self.data[o:o + n]

	# -- names -------------------------------------------------------------

	def names(self):
		"""(family, subfamily, full name, PostScript name), any may be ''."""
		b = self.table("name")
		out = {}
		if not b:
			return ("", "", "", "")
		try:
			count = _u16(b, 2)
			strOff = _u16(b, 4)
			for i in range(count):
				r = 6 + 12 * i
				pid, eid, lang, nid, ln, so = (_u16(b, r + k) for k in range(0, 12, 2))
				if nid not in (1, 2, 4, 6, 16, 17):
					continue
				raw = b[strOff + so:strOff + so + ln]
				if pid == 3 or pid == 0:
					s = raw.decode("utf-16-be", "replace")
				else:
					s = raw.decode("latin-1", "replace")
				# prefer English (Windows 0x409) names
				if nid not in out or (pid == 3 and lang == 0x409):
					out[nid] = s
		except Exception:
			pass
		return (out.get(16) or out.get(1, ""), out.get(17) or out.get(2, ""), out.get(4, ""), out.get(6, ""))

	# -- metrics -------------------------------------------------------------

	def unitsPerEm(self):
		b = self.table("head")
		return _u16(b, 18) if b else 1000

	def advances(self):
		hhea = self.table("hhea")
		hmtx = self.table("hmtx")
		if not hhea or not hmtx:
			return [0] * self.numGlyphs
		n = _u16(hhea, 34)
		out = []
		last = 0
		for g in range(self.numGlyphs):
			if g < n:
				if 4 * g + 2 > len(hmtx):
					out.append(last)
					continue
				last = _u16(hmtx, 4 * g)
			out.append(last)
		return out

	# -- cmap -------------------------------------------------------------

	def cmap(self):
		"""{codepoint: glyph id} from the best Unicode (or symbol) subtable."""
		b = self.table("cmap")
		res = {}
		if not b:
			return res
		try:
			n = _u16(b, 2)
			subs = []
			for i in range(n):
				pid, eid, off = _u16(b, 4 + 8 * i), _u16(b, 6 + 8 * i), _u32(b, 8 + 8 * i)
				rank = {(3, 10): 0, (0, 4): 1, (3, 1): 2, (0, 3): 3, (0, 1): 4, (0, 0): 5, (3, 0): 6, (1, 0): 7}.get((pid, eid), 8)
				subs.append((rank, pid, eid, off))
			uni = [x for x in subs if x[0] <= 5]
			for rank, pid, eid, off in sorted(uni or subs, reverse=True):
				m = self._cmapSub(b, off)
				res.update(m)
		except Exception:
			pass
		return res

	def cmapTables(self):
		"""{(platform, encoding): {code: glyph id}} for every cmap subtable."""
		b = self.table("cmap")
		res = {}
		if not b:
			return res
		try:
			for i in range(_u16(b, 2)):
				pid, eid, off = _u16(b, 4 + 8 * i), _u16(b, 6 + 8 * i), _u32(b, 8 + 8 * i)
				try:
					res[(pid, eid)] = self._cmapSub(b, off)
				except Exception:
					pass
		except Exception:
			pass
		return res

	@staticmethod
	def _cmapSub(b, off):
		fmt = _u16(b, off)
		m = {}
		if fmt == 4:
			segX2 = _u16(b, off + 6)
			ends = off + 14
			starts = ends + segX2 + 2
			deltas = starts + segX2
			ranges = deltas + segX2
			for s in range(segX2 // 2):
				end = _u16(b, ends + 2 * s)
				start = _u16(b, starts + 2 * s)
				delta = _s16(b, deltas + 2 * s)
				ro = _u16(b, ranges + 2 * s)
				if start == 0xFFFF:
					continue
				for c in range(start, end + 1):
					if ro == 0:
						g = (c + delta) & 0xFFFF
					else:
						p = ranges + 2 * s + ro + 2 * (c - start)
						if p + 2 > len(b):
							continue
						g = _u16(b, p)
						if g:
							g = (g + delta) & 0xFFFF
					if g:
						m[c] = g
		elif fmt == 12:
			n = _u32(b, off + 12)
			for i in range(n):
				r = off + 16 + 12 * i
				s, e, g = _u32(b, r), _u32(b, r + 4), _u32(b, r + 8)
				if e - s > 70000:
					continue
				for c in range(s, e + 1):
					m[c] = g + c - s
		elif fmt == 0:
			for c in range(256):
				g = b[off + 6 + c]
				if g:
					m[c] = g
		elif fmt == 6:
			first, count = _u16(b, off + 6), _u16(b, off + 8)
			for i in range(count):
				g = _u16(b, off + 10 + 2 * i)
				if g:
					m[first + i] = g
		return m

	# -- outlines -------------------------------------------------------------

	def _glyphData(self, gid):
		if self._loca is None:
			head = self.table("head")
			loca = self.table("loca")
			if not head or not loca or "glyf" not in self.tables:
				self._loca = []
			else:
				longFmt = _s16(head, 50) == 1
				n = self.numGlyphs + 1
				if longFmt:
					self._loca = list(struct.unpack_from(">%dI" % min(n, len(loca) // 4), loca, 0))
				else:
					self._loca = [2 * v for v in struct.unpack_from(">%dH" % min(n, len(loca) // 2), loca, 0)]
		if gid + 1 >= len(self._loca):
			return b""
		go = self.tables["glyf"][0]
		a, z = self._loca[gid], self._loca[gid + 1]
		if z <= a:
			return b""
		return self.data[go + a:go + z]

	def glyphHash(self, gid, _depth=0):
		"""A short fingerprint of a glyph's outline (the same in the full font and in a PDF subset)."""
		h = self._hashes.get(gid)
		if h is not None:
			return h or None
		h = ""
		try:
			h = self._hashGlyph(gid, _depth)
		except Exception:
			h = ""
		self._hashes[gid] = h
		return h or None

	def _hashGlyph(self, gid, depth):
		b = self._glyphData(gid)
		if len(b) < 10:
			return ""
		nc = _s16(b, 0)
		if nc == 0:
			return ""
		if nc > 0:
			ends = struct.unpack_from(">%dH" % nc, b, 10)
			nPts = ends[-1] + 1
			p = 10 + 2 * nc
			insLen = _u16(b, p)
			p += 2 + insLen
			flags = []
			while len(flags) < nPts:
				f = b[p]
				p += 1
				flags.append(f)
				if f & 8:
					r = b[p]
					p += 1
					flags.extend([f] * r)
			flags = flags[:nPts]
			xs = []
			v = 0
			for f in flags:
				if f & 2:
					d = b[p]
					p += 1
					v += d if f & 16 else -d
				elif not f & 16:
					v += _s16(b, p)
					p += 2
				xs.append(v)
			ys = []
			v = 0
			for f in flags:
				if f & 4:
					d = b[p]
					p += 1
					v += d if f & 32 else -d
				elif not f & 32:
					v += _s16(b, p)
					p += 2
				ys.append(v)
			on = bytes(f & 1 for f in flags)
			key = struct.pack(">%dH" % nc, *ends) + struct.pack(">%di" % nPts, *xs) + struct.pack(">%di" % nPts, *ys) + on
		else:
			if depth > 6:
				return ""
			parts = []
			p = 10
			while True:
				fl = _u16(b, p)
				cg = _u16(b, p + 2)
				p += 4
				if fl & 1:
					a1, a2 = _s16(b, p), _s16(b, p + 2)
					p += 4
				else:
					a1, a2 = b[p], b[p + 1]
					if fl & 2:
						a1 = a1 - 256 if a1 > 127 else a1
						a2 = a2 - 256 if a2 > 127 else a2
					p += 2
				tr = ()
				if fl & 8:
					tr = (_s16(b, p),)
					p += 2
				elif fl & 0x40:
					tr = (_s16(b, p), _s16(b, p + 2))
					p += 4
				elif fl & 0x80:
					tr = tuple(_s16(b, p + 2 * k) for k in range(4))
					p += 8
				sub = self.glyphHash(cg, depth + 1) or "-"
				parts.append("%s,%d,%d,%d,%r" % (sub, fl & 2, a1, a2, tr))
				if not fl & 0x20:
					break
			key = "|".join(parts).encode("ascii")
		return hashlib.md5(key).hexdigest()[:12]

	def hasHeadLine(self, gid):
		"""True if the glyph has a long straight bar along its top, like the Devanagari head line
		(shirorekha). Latin lower-case letters never do."""
		b = self._glyphData(gid)
		if len(b) < 12 or _s16(b, 0) <= 0:
			return False
		try:
			nc = _s16(b, 0)
			yMax = _s16(b, 8)
			ends = struct.unpack_from(">%dH" % nc, b, 10)
			nPts = ends[-1] + 1
			p = 10 + 2 * nc
			p += 2 + _u16(b, p)
			flags = []
			while len(flags) < nPts:
				f = b[p]
				p += 1
				flags.append(f)
				if f & 8:
					flags.extend([f] * b[p])
					p += 1
			flags = flags[:nPts]
			xs = []
			v = 0
			for f in flags:
				if f & 2:
					v += b[p] if f & 16 else -b[p]
					p += 1
				elif not f & 16:
					v += _s16(b, p)
					p += 2
				xs.append(v)
			ys = []
			v = 0
			for f in flags:
				if f & 4:
					v += b[p] if f & 32 else -b[p]
					p += 1
				elif not f & 32:
					v += _s16(b, p)
					p += 2
				ys.append(v)
		except Exception:
			return False
		upm = self.unitsPerEm()
		xMin, xMax = min(xs), max(xs)
		width = xMax - xMin
		if width <= 0:
			return False
		# horizontal edges in the top band of the glyph
		band = 0.08 * upm
		start = 0
		longest = 0
		for e in ends:
			pts = list(zip(xs[start:e + 1], ys[start:e + 1]))
			start = e + 1
			for k in range(len(pts)):
				(x1, y1), (x2, y2) = pts[k], pts[(k + 1) % len(pts)]
				if abs(y1 - y2) <= 0.01 * upm and y1 >= yMax - band and y2 >= yMax - band:
					longest = max(longest, abs(x2 - x1))
		return longest >= 0.6 * width and width >= 0.3 * upm

	# -- letters behind each glyph (cmap + GSUB) ----------------------------------

	def glyphStrings(self):
		"""{glyph id: the Unicode text this glyph shows}, from the cmap and the GSUB substitutions."""
		cm = self.cmap()
		s = {}
		for cp, g in sorted(cm.items(), key=lambda x: (not (0x900 <= x[0] <= 0x97F), x[0])):
			if cp < 0x20 or 0xF000 <= cp <= 0xF0FF:
				continue
			if g not in s:
				s[g] = chr(cp)
		b = self.table("GSUB")
		if not b:
			return s
		try:
			subs = self._gsubSubtables(b)
		except Exception:
			return s
		# ligatures first in every round: a reph made from र + ् must not take the text of a
		# single substitution that also leads to it (Rajdhani's reph would read ृ)
		subs = [x for x in subs if x[0] == 4] + [x for x in subs if x[0] != 4]
		for _round in range(12):
			changed = False
			for typ, data, below in subs:
				if typ == 1:
					for a, z in data:
						if a in s and z not in s:
							s[z] = s[a]
							changed = True
				elif typ == 3:
					for a, alts in data:
						if a in s:
							for z in alts:
								if z not in s:
									s[z] = s[a]
									changed = True
				elif typ == 4:
					for first, comps, lig in data:
						if lig in s or first not in s:
							continue
						if all(c in s for c in comps):
							v = s[first] + "".join(s[c] for c in comps)
							if below and len(v) == 2 and v[1] == VIRAMA:
								v = v[::-1]  # below-base / post-base form: ra + virama stands for "्र"
							s[lig] = v
							changed = True
			if not changed:
				break
		return s

	def _gsubSubtables(self, b):
		featList = _u16(b, 6)
		lookupList = _u16(b, 8)
		feat = {}
		n = _u16(b, featList)
		for i in range(n):
			tag = b[featList + 2 + 6 * i:featList + 6 + 6 * i].decode("latin-1")
			fo = featList + _u16(b, featList + 6 + 6 * i)
			cnt = _u16(b, fo + 2)
			for k in range(cnt):
				feat.setdefault(_u16(b, fo + 4 + 2 * k), set()).add(tag)
		out = []
		nl = _u16(b, lookupList)
		for li in range(nl):
			lo = lookupList + _u16(b, lookupList + 2 + 2 * li)
			typ = _u16(b, lo)
			cnt = _u16(b, lo + 4)
			below = bool(feat.get(li, set()) & {"blwf", "pstf", "vatu"})
			for k in range(cnt):
				so = lo + _u16(b, lo + 6 + 2 * k)
				t = typ
				if t == 7:
					t = _u16(b, so + 2)
					so = so + _u32(b, so + 4)
				try:
					d = self._readSub(b, t, so)
				except Exception:
					d = None
				if d:
					out.append((t, d, below))
		return out

	@staticmethod
	def _coverage(b, o):
		fmt = _u16(b, o)
		if fmt == 1:
			n = _u16(b, o + 2)
			return [_u16(b, o + 4 + 2 * i) for i in range(n)]
		res = []
		n = _u16(b, o + 2)
		for i in range(n):
			r = o + 4 + 6 * i
			s, e = _u16(b, r), _u16(b, r + 2)
			res.extend(range(s, e + 1))
		return res

	def _readSub(self, b, t, so):
		fmt = _u16(b, so)
		if t == 1:
			cov = self._coverage(b, so + _u16(b, so + 2))
			if fmt == 1:
				d = _s16(b, so + 4)
				return [(g, (g + d) & 0xFFFF) for g in cov]
			n = _u16(b, so + 4)
			return [(g, _u16(b, so + 6 + 2 * i)) for i, g in enumerate(cov[:n])]
		if t == 3:
			cov = self._coverage(b, so + _u16(b, so + 2))
			n = _u16(b, so + 4)
			res = []
			for i, g in enumerate(cov[:n]):
				ao = so + _u16(b, so + 6 + 2 * i)
				c = _u16(b, ao)
				res.append((g, [_u16(b, ao + 2 + 2 * k) for k in range(c)]))
			return res
		if t == 4:
			cov = self._coverage(b, so + _u16(b, so + 2))
			n = _u16(b, so + 4)
			res = []
			for i, g in enumerate(cov[:n]):
				lso = so + _u16(b, so + 6 + 2 * i)
				ln = _u16(b, lso)
				for k in range(ln):
					lo = lso + _u16(b, lso + 2 + 2 * k)
					lig = _u16(b, lo)
					cc = _u16(b, lo + 2)
					comps = [_u16(b, lo + 4 + 2 * m) for m in range(cc - 1)]
					res.append((g, comps, lig))
			return res
		return None


def readTables(path, tags):
	"""The font file with only some tables read (the rest left as zero bytes): quick for big fonts."""
	import os
	size = os.path.getsize(path)
	with open(path, "rb") as fh:
		head = fh.read(12)
		if size < 4 * 1024 * 1024:
			return head + fh.read()
		buf = bytearray(size)
		fh.seek(0)
		first = fh.read(65536)
		buf[:len(first)] = first
		offs = [0]
		if first[:4] == b"ttcf":
			n = _u32(first, 8)
			offs = [_u32(first, 12 + 4 * i) for i in range(min(n, 8))]
		for off in offs:
			fh.seek(off)
			hdr = fh.read(12)
			numTables = _u16(hdr, 4)
			fh.seek(off)
			d = fh.read(12 + 16 * numTables)
			buf[off:off + len(d)] = d
			for i in range(numTables):
				rec = 12 + 16 * i
				tag = d[rec:rec + 4].decode("latin-1")
				if tag in tags:
					o, ln = _u32(d, rec + 8), _u32(d, rec + 12)
					fh.seek(o)
					chunk = fh.read(ln)
					buf[o:o + len(chunk)] = chunk
		return bytes(buf)


def faceCount(data):
	if data[:4] == b"ttcf":
		return _u32(data, 8)
	return 1


def referenceTable(font):
	"""(unitsPerEm, [ (text or None, advance, outline hash or None) per glyph ])"""
	strings = font.glyphStrings()
	adv = font.advances()
	return font.unitsPerEm(), [(strings.get(g), adv[g] if g < len(adv) else 0, font.glyphHash(g)) for g in range(font.numGlyphs)]
