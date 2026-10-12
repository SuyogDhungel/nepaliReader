# -*- coding: UTF-8 -*-
# Nepali Reader: the layout of a PDF - its tables (rows, columns, header cells, merged cells),
# headings and paragraphs - so a table is read and copied as a table.
#
# Two sources, both exact for what they cover:
#   * the PDF's own tags (Word, LibreOffice and most office programs save them): which words are
#     in which table cell, heading or paragraph;
#   * the cell borders drawn on the page: a table without tags is rebuilt from its lines, and the
#     drawn borders also show which cells of a tagged table are merged.
# A table with neither (no tags, no lines) stays plain text.

import re

try:
	from . import pdfReader
except ImportError:
	import pdfReader

_ID = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _mul(a, b):
	return (
		a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
		a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
		a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5],
	)


def _pt(m, x, y):
	return (x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5])


# ---------------------------------------------------------------- pages


def pageRefs(doc):
	"""The object reference of every page, in the order of doc.pages()."""
	r = doc.resolve
	root = r(doc.trailer.get("Root")) or {}
	out = []
	seen = set()

	def walk(ref, depth):
		node = r(ref)
		if not isinstance(node, dict) or depth > 40 or id(node) in seen:
			return
		seen.add(id(node))
		kids = r(node.get("Kids"))
		if node.get("Type") == "Pages" or (isinstance(kids, list) and node.get("Type") != "Page"):
			for k in kids or []:
				walk(k, depth + 1)
		else:
			out.append(tuple(ref) if isinstance(ref, pdfReader.Ref) else None)

	walk(root.get("Pages"), 0)
	return out


# ---------------------------------------------------------------- tags

_HEADINGS = {"H": 2, "H1": 1, "H2": 2, "H3": 3, "H4": 4, "H5": 5, "H6": 6, "Title": 1}
_BLOCKS = {"P", "LI", "Lbl", "LBody", "Caption", "BlockQuote", "Note", "TOCI", "Code", "Figure", "Formula", "TH", "TD"}
_STANDARD = set(_HEADINGS) | _BLOCKS | {"Table", "TR", "THead", "TBody", "TFoot", "L", "Span", "Sect", "Div", "Part",
	"Art", "Document", "Link", "Quote", "Reference", "BibEntry", "Annot", "Ruby", "Warichu", "TOC", "Index",
	"NonStruct", "Private", "Form"}


def _spans(r, el):
	"""(row span, column span) of a tagged table cell (its /A attributes, default 1)."""
	rs = cs = 1
	a = r(el.get("A"))
	for d in (a if isinstance(a, list) else [a]):
		d = r(d)
		if isinstance(d, dict):
			v = r(d.get("RowSpan"))
			if isinstance(v, int) and 1 < v < 1000:
				rs = v
			v = r(d.get("ColSpan"))
			if isinstance(v, int) and 1 < v < 1000:
				cs = v
	return rs, cs


def structure(doc, refs, deadline=None):
	"""What the PDF's tags say, or None for an untagged PDF:
	{"mc": {(page, mcid): (block, heading level, (table, row, cell) or None)},
	 "tables": [[[{"th", "rs", "cs"}...] per row] per table]}"""
	import time
	r = doc.resolve
	root = r(doc.trailer.get("Root")) or {}
	st = r(root.get("StructTreeRoot"))
	if not isinstance(st, dict):
		return None
	roleMap = r(st.get("RoleMap"))
	roleMap = roleMap if isinstance(roleMap, dict) else {}
	pageOf = {ref: i for i, ref in enumerate(refs) if ref is not None}

	def role(s):
		for _i in range(6):
			if s in _STANDARD:
				return s
			t = roleMap.get(s)
			t = r(t)
			if not isinstance(t, str):
				return s
			s = str(t)
		return s

	mc = {}
	tables = []
	counter = [0]
	seen = set()
	steps = [0]

	def newBlock():
		counter[0] += 1
		return counter[0]

	def walk(node, pg, block, head, cell, table, row, depth):
		if depth > 120:
			return
		steps[0] += 1
		if deadline and not steps[0] & 1023 and time.monotonic() > deadline:
			raise TimeoutError
		if isinstance(node, pdfReader.Ref):
			if node in seen:
				return
			seen.add(node)
		node = r(node)
		if isinstance(node, list):
			for k in node:
				walk(k, pg, block, head, cell, table, row, depth + 1)
			return
		if isinstance(node, int):
			if pg is not None:
				mc[(pg, node)] = (block, head, cell)
			return
		if not isinstance(node, dict):
			return
		p = node.get("Pg")
		if isinstance(p, pdfReader.Ref):
			pg = pageOf.get(tuple(p), pg)
		if "MCID" in node:
			# a marked-content reference (MCR), possibly on another page
			m = r(node.get("MCID"))
			if isinstance(m, int) and pg is not None:
				mc[(pg, m)] = (block, head, cell)
			return
		if r(node.get("Type")) == "OBJR":
			return
		s = node.get("S")
		tag = role(str(r(s))) if s is not None else ""
		if tag == "Table":
			table = len(tables)
			tables.append([])
			row = None
		elif tag == "TR" and table is not None:
			tables[table].append([])
			row = len(tables[table]) - 1
		elif tag in ("TH", "TD") and table is not None:
			if row is None:
				tables[table].append([])
				row = len(tables[table]) - 1
			rs, cs = _spans(r, node)
			cells = tables[table][row]
			cells.append({"th": tag == "TH", "rs": rs, "cs": cs})
			cell = (table, row, len(cells) - 1)
		if tag in _HEADINGS:
			head = _HEADINGS[tag]
		if tag in _HEADINGS or tag in _BLOCKS:
			block = newBlock()
		k = node.get("K")
		if k is not None:
			walk(k, pg, block, head, cell, table, row, depth + 1)

	try:
		walk(st.get("K"), None, 0, 0, None, None, None, 0)
	except (TimeoutError, RecursionError):
		pass
	if not mc:
		return None
	return {"mc": mc, "tables": tables}


def _gridOfRows(rows):
	"""Row/column places of tagged cells, rows given as lists of {"rs", "cs"} (HTML rules: a cell
	goes to the first column not taken by a cell above that spans down)."""
	taken = set()
	out = []
	for ri, cells in enumerate(rows):
		c = 0
		for ci, cell in enumerate(cells):
			while (ri, c) in taken:
				c += 1
			for dr in range(cell["rs"]):
				for dc in range(cell["cs"]):
					taken.add((ri + dr, c + dc))
			out.append((ri, ci, c))
			c += cell["cs"]
	return out


# ---------------------------------------------------------------- drawn lines


def rulings(doc, data, res, deadline=None, depth=0, ctm=_ID, out=None):
	"""Horizontal and vertical lines drawn on a page: ([(y, x0, x1)], [(x, y0, y1)])."""
	import time
	r = doc.resolve
	if out is None:
		out = ([], [])
	hs, vs = out
	res = r(res) if res is not None else {}
	if not isinstance(res, dict):
		res = {}
	stack = []
	path = []    # finished pieces: ("re", x0, y0, x1, y1) or ("l", (x, y), (x, y)); in page space
	sub = []     # points of the open subpath
	start = None
	count = 0
	for op, args in pdfReader.contentOps(data, graphics=True):
		count += 1
		if count & 1023 == 0 and deadline and time.monotonic() > deadline:
			raise TimeoutError
		if op == "re" and len(args) >= 4:
			x, y, w, h = args[:4]
			pts = [_pt(ctm, x, y), _pt(ctm, x + w, y), _pt(ctm, x + w, y + h), _pt(ctm, x, y + h)]
			xs = [p[0] for p in pts]
			ys = [p[1] for p in pts]
			path.append(("re", min(xs), min(ys), max(xs), max(ys)))
			sub = []
		elif op == "m" and len(args) >= 2:
			start = _pt(ctm, args[0], args[1])
			sub = [start]
		elif op == "l" and len(args) >= 2 and sub:
			p = _pt(ctm, args[0], args[1])
			path.append(("l", sub[-1], p))
			sub.append(p)
		elif op == "h" and sub and start is not None:
			path.append(("l", sub[-1], start))
			sub.append(start)
		elif op in ("c", "v", "y"):
			if len(args) >= 2:
				sub.append(_pt(ctm, args[-2], args[-1]))
		elif op in ("S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"):
			fill = op in ("f", "F", "f*", "B", "B*", "b", "b*")
			stroke = op in ("S", "s", "B", "B*", "b", "b*")
			if fill or stroke:
				_paint(path, fill, stroke, hs, vs)
			path = []
			sub = []
			start = None
		elif op == "cm" and len(args) >= 6:
			ctm = _mul(tuple(float(a) for a in args[:6]), ctm)
		elif op == "q":
			stack.append(ctm)
		elif op == "Q":
			if stack:
				ctm = stack.pop()
		elif op == "Do" and args and depth < 4:
			xo = r((r(res.get("XObject")) or {}).get(args[0]))
			if isinstance(xo, pdfReader.Stream) and r(xo.dict.get("Subtype")) == "Form":
				mat = r(xo.dict.get("Matrix"))
				fm = tuple(float(r(a)) for a in mat[:6]) if isinstance(mat, list) and len(mat) >= 6 else _ID
				try:
					sub_data = doc.decode(xo)
				except Exception:
					continue
				rulings(doc, sub_data, xo.dict.get("Resources") or res, deadline, depth + 1, _mul(fm, ctm), out)
	return out


def _paint(path, fill, stroke, hs, vs):
	lines = [p for p in path if p[0] == "l"]
	rects = [p for p in path if p[0] == "re"]
	if fill and not stroke and lines and len(lines) <= 5:
		# a thin rectangle drawn with lines (m l l l h f)
		xs = [c for p in lines for c in (p[1][0], p[2][0])]
		ys = [c for p in lines for c in (p[1][1], p[2][1])]
		if all(abs(p[1][0] - p[2][0]) < 0.5 or abs(p[1][1] - p[2][1]) < 0.5 for p in lines):
			rects.append(("re", min(xs), min(ys), max(xs), max(ys)))
			lines = []
	for _t, x0, y0, x1, y1 in rects:
		w = x1 - x0
		h = y1 - y0
		if fill and h <= 3.0 and w > 3.0:
			hs.append(((y0 + y1) / 2.0, x0, x1))
		elif fill and w <= 3.0 and h > 3.0:
			vs.append(((x0 + x1) / 2.0, y0, y1))
		elif stroke:
			if w > 3.0:
				hs.append((y0, x0, x1))
				hs.append((y1, x0, x1))
			if h > 3.0:
				vs.append((x0, y0, y1))
				vs.append((x1, y0, y1))
	if stroke:
		for _t, a, b in lines:
			if abs(a[1] - b[1]) <= 1.0 and abs(a[0] - b[0]) > 3.0:
				hs.append(((a[1] + b[1]) / 2.0, min(a[0], b[0]), max(a[0], b[0])))
			elif abs(a[0] - b[0]) <= 1.0 and abs(a[1] - b[1]) > 3.0:
				vs.append(((a[0] + b[0]) / 2.0, min(a[1], b[1]), max(a[1], b[1])))


def _merge(segs, tol=2.0, gap=3.0):
	"""Lines on (nearly) the same row joined where they touch: [(pos, a, b)]."""
	out = []
	segs = sorted(segs)
	i = 0
	while i < len(segs):
		j = i
		group = []
		pos0 = segs[i][0]
		while j < len(segs) and segs[j][0] - pos0 <= tol:
			group.append(segs[j])
			j += 1
		pos = sum(s[0] for s in group) / len(group)
		group.sort(key=lambda s: s[1])
		a, b = group[0][1], group[0][2]
		for s in group[1:]:
			if s[1] <= b + gap:
				b = max(b, s[2])
			else:
				out.append((pos, a, b))
				a, b = s[1], s[2]
		out.append((pos, a, b))
		i = j
	return [s for s in out if s[2] - s[1] >= 4.0]


def gridTables(hs, vs):
	"""Tables drawn with lines: [{"cells": [(x0, y0, x1, y1, row, col, rowspan, colspan)], "nr", "nc"}]."""
	H = _merge(hs)
	V = _merge(vs)
	if len(H) < 2 or len(V) < 2 or len(H) * len(V) > 250000:
		return []
	tol = 2.0
	byH = {}
	byV = {}
	pts = set()
	for hi, (y, x0, x1) in enumerate(H):
		for vi, (x, y0, y1) in enumerate(V):
			if x0 - tol <= x <= x1 + tol and y0 - tol <= y <= y1 + tol:
				pts.add((vi, hi))
				byH.setdefault(hi, []).append(vi)
				byV.setdefault(vi, []).append(hi)
	for hi in byH:
		byH[hi].sort(key=lambda vi: V[vi][0])
	for vi in byV:
		byV[vi].sort(key=lambda hi: -H[hi][0])
	cells = []
	for (vi, hi) in pts:
		x, y = V[vi][0], H[hi][0]
		below = [h2 for h2 in byV[vi] if H[h2][0] < y - tol]
		right = [v2 for v2 in byH[hi] if V[v2][0] > x + tol]
		found = None
		for h2 in below:
			for v2 in right:
				if (v2, h2) in pts:
					found = (v2, h2)
					break
			if found:
				break
		if found:
			v2, h2 = found
			cells.append((x, H[h2][0], V[v2][0], y, (vi, hi), (v2, h2), (vi, h2), (v2, hi)))
	if len(cells) < 2:
		return []
	# cells that share a corner belong to one table
	parent = list(range(len(cells)))

	def find(a):
		while parent[a] != a:
			parent[a] = parent[parent[a]]
			a = parent[a]
		return a

	owner = {}
	for i, c in enumerate(cells):
		for corner in c[4:]:
			j = owner.get(corner)
			if j is None:
				owner[corner] = i
			else:
				parent[find(i)] = find(j)
	groups = {}
	for i in range(len(cells)):
		groups.setdefault(find(i), []).append(cells[i])
	out = []
	for group in groups.values():
		xs = _snap(sorted({c[0] for c in group} | {c[2] for c in group}))
		ys = _snap(sorted({c[1] for c in group} | {c[3] for c in group}), reverse=True)
		nc = len(xs) - 1
		nr = len(ys) - 1
		if nr < 2 or nc < 2 or len(group) < 3:
			continue
		tc = []
		for x0, y0, x1, y1 in (c[:4] for c in group):
			c0 = _index(xs, x0)
			c1 = _index(xs, x1)
			r0 = _index(ys, y1)
			r1 = _index(ys, y0)
			if c1 <= c0 or r1 <= r0:
				continue
			tc.append((x0, y0, x1, y1, r0, c0, r1 - r0, c1 - c0))
		tc.sort(key=lambda c: (c[4], c[5]))
		out.append({"cells": tc, "nr": nr, "nc": nc})
	return out


def _snap(vals, reverse=False):
	out = []
	for v in vals:
		if not out or abs(v - out[-1]) > 1.5:
			out.append(v)
	return out[::-1] if reverse else out


def _index(vals, v):
	best = 0
	for i, x in enumerate(vals):
		if abs(x - v) < abs(vals[best] - v):
			best = i
	return best


# ---------------------------------------------------------------- the layout of a document


def wordBox(w):
	"""(page, x0, y0, x1, y1, mcid) of a grouped word (its glyphs carry page positions)."""
	xs0 = []
	xs1 = []
	ys = []
	size = 0.0
	mcids = {}
	for g in w.glyphs:
		if len(g) < 10:
			continue
		x, y = g[8], g[9]
		xs0.append(x)
		xs1.append(x + max(g[5], 0.0))
		ys.append(y)
		size = max(size, g[4] or 0.0)
		if g[7] is not None:
			mcids[g[7]] = mcids.get(g[7], 0) + 1
	if not xs0:
		return None
	pn = w.page[0] if isinstance(w.page, tuple) else w.page
	mcid = max(mcids, key=mcids.get) if mcids else None
	y = sum(ys) / len(ys)
	return (pn, min(xs0), y - 0.25 * size, max(xs1), y + 0.75 * size, mcid)


def analyse(struct, pageTables, boxes, order):
	"""The layout kept in the index.
	struct: structure() or None; pageTables: {page: gridTables()}; boxes: wordBox() of every
	grouped word; order: the index position of every grouped word (None if it is not in the index).
	Returns {"tables": [...], "blocks": [...] or None, "heads": {block: level}}."""
	n = max((i for i in order if i is not None), default=-1) + 1
	tables = []
	blocks = None
	heads = {}
	tagCell = {}   # index word -> (tagged table, row, cell)
	if struct:
		blocks = [0] * n
		mc = struct["mc"]
		for wi, box in enumerate(boxes):
			i = order[wi]
			if i is None or box is None or box[5] is None:
				continue
			info = mc.get((box[0], box[5]))
			if info is None:
				continue
			block, head, cell = info
			blocks[i] = block
			if head:
				heads[block] = head
			if cell is not None:
				tagCell[i] = cell
	# tables drawn with lines: the words inside each cell
	used = set()
	byPage = {}
	for wi, box in enumerate(boxes):
		if box is not None and order[wi] is not None:
			byPage.setdefault(box[0], []).append((order[wi], box))
	for pn, tlist in sorted(pageTables.items()):
		for t in tlist:
			if not _wholeTable(t, byPage.get(pn, ()), used):
				continue
			cells = []
			filled = 0
			for (x0, y0, x1, y1, r0, c0, rs, cs) in t["cells"]:
				ws = []
				for i, box in byPage.get(pn, ()):
					if i in used:
						continue
					cx = (box[1] + box[3]) / 2.0
					cy = (box[2] + box[4]) / 2.0
					if x0 - 1.0 <= cx <= x1 + 1.0 and y0 - 1.0 <= cy <= y1 + 1.0:
						ws.append(i)
				ws.sort()
				used.update(ws)
				if ws:
					filled += 1
				th = bool(ws) and sum(1 for i in ws if i in tagCell and struct["tables"][tagCell[i][0]][tagCell[i][1]][tagCell[i][2]]["th"]) * 2 > len(ws)
				cells.append([r0, c0, rs, cs, 1 if th else 0, ws])
			if filled < 2:
				for c in cells:
					used.difference_update(c[5])
				continue
			tables.append({"p": pn, "nr": t["nr"], "nc": t["nc"], "cells": cells})
	# tagged tables without lines: the cells the tags give
	if struct:
		byTag = {}
		for i, cell in tagCell.items():
			if i in used:
				continue
			byTag.setdefault(cell[0], {}).setdefault((cell[1], cell[2]), []).append(i)
		for ti, cellWords in sorted(byTag.items()):
			rows = struct["tables"][ti]
			if len(rows) < 2 or len(cellWords) < 2:
				continue
			cells = []
			ncols = 0
			for (ri, ci, col) in _gridOfRows(rows):
				info = rows[ri][ci]
				ws = sorted(cellWords.get((ri, ci), []))
				cells.append([ri, col, info["rs"], info["cs"], 1 if info["th"] else 0, ws])
				ncols = max(ncols, col + info["cs"])
			allWords = [i for c in cells for i in c[5]]
			pn = boxes[order.index(min(allWords))][0] if allWords and min(allWords) in order else 0
			tables.append({"p": pn, "nr": len(rows), "nc": ncols, "cells": cells})
	tables.sort(key=lambda t: min((i for c in t["cells"] for i in c[5]), default=0))
	return {"tables": tables, "blocks": blocks, "heads": heads}


def _wholeTable(t, words, used):
	"""A grid of lines is taken as a table only when it holds the text around it: no words right
	beside it on its rows, and none inside it that are in no cell (a picture-like layout with a
	few boxes would otherwise give a table with pieces missing)."""
	x0 = min(c[0] for c in t["cells"])
	y0 = min(c[1] for c in t["cells"])
	x1 = max(c[2] for c in t["cells"])
	y1 = max(c[3] for c in t["cells"])
	inside = beside = loose = 0
	for i, box in words:
		if i in used:
			continue
		cx = (box[1] + box[3]) / 2.0
		cy = (box[2] + box[4]) / 2.0
		if not (y0 + 1.0 <= cy <= y1 - 1.0):
			continue
		if x0 - 1.0 <= cx <= x1 + 1.0:
			if any(c[0] - 1.0 <= cx <= c[2] + 1.0 and c[1] - 1.0 <= cy <= c[3] + 1.0 for c in t["cells"]):
				inside += 1
			else:
				loose += 1
		elif (x0 - box[3] if cx < x0 else box[1] - x1) < 12.0:
			beside += 1  # (text farther away is another column of the page)
	if not inside:
		return False
	return (beside + loose) * 10 <= inside


# ---------------------------------------------------------------- reading the layout


def cellIndex(layout):
	"""index word -> (table number, cell number)."""
	out = {}
	for ti, t in enumerate(layout.get("tables") or ()):
		for ci, c in enumerate(t["cells"]):
			for i in c[5]:
				out[i] = (ti, ci)
	return out


def _wordText(w):
	return w[0] if w[0] is not None else w[3]


def _esc(s):
	return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _tableRows(t, words, only=None):
	"""Rows of (cell, text) for a table; with only, just the rows holding those words and only
	those words in each cell."""
	rows = {}
	for c in t["cells"]:
		ws = c[5] if only is None else [i for i in c[5] if i in only]
		rows.setdefault(c[0], []).append((c, " ".join(_wordText(words[i]) for i in ws)))
	if only is not None:
		keep = {c[0] for c in t["cells"] if any(i in only for i in c[5])}
		rows = {r: v for r, v in rows.items() if r in keep}
	return [sorted(v, key=lambda x: x[0][1]) for _r, v in sorted(rows.items())]


def tableHtml(t, words, only=None):
	out = ["<table>"]
	for row in _tableRows(t, words, only):
		out.append("<tr>")
		for c, text in row:
			tag = "th" if c[4] else "td"
			attrs = ""
			if c[2] > 1:
				attrs += ' rowspan="%d"' % c[2]
			if c[3] > 1:
				attrs += ' colspan="%d"' % c[3]
			out.append("<%s%s>%s</%s>" % (tag, attrs, _esc(text), tag))
		out.append("</tr>")
	out.append("</table>")
	return "".join(out)


def tableText(t, words, only=None):
	"""One row per line, cells separated by tabs (a merged cell's text is in its first row and
	column; the places it covers are left empty, as a spreadsheet does)."""
	lines = []
	for row in _tableRows(t, words, only):
		line = []
		col = 0
		for c, text in row:
			while col < c[1]:
				line.append("")
				col += 1
			line.append(text.replace("\t", " "))
			col += c[3]
			for _k in range(c[3] - 1):
				line.append("")
		lines.append("\t".join(line).rstrip("\t"))
	return "\r\n".join(lines)


def _lineGroups(idx, ids, cells):
	"""Pieces of a run of index words in reading order: ("text", block, [words]) or ("table", n)."""
	layout = getattr(idx, "layout", None) or {}
	blocks = layout.get("blocks")
	out = []
	doneTables = set()
	cur = None
	for i in ids:
		tc = cells.get(i)
		if tc is not None:
			if tc[0] not in doneTables:
				doneTables.add(tc[0])
				out.append(("table", tc[0]))
			cur = None
			continue
		key = blocks[i] if blocks and i < len(blocks) and blocks[i] else None
		newLine = cur is None or (key is not None and key != cur[1]) or (key is None and idx.lineStart[i]) or (key is not None and cur[1] is None)
		if newLine:
			cur = ["text", key, []]
			out.append(cur)
		cur[2].append(i)
	return out


def clipLines(idx, items):
	"""(plain text, html) for copying lines of a PDF that take in cells of a table, or None.
	items: (text of the line, index words it was found at) for every copied line. A line whose
	words are in a table is part of that table (shown once, with the selected cells); any other
	line is copied as its text."""
	layout = getattr(idx, "layout", None)
	if not layout or not layout.get("tables"):
		return None
	cells = cellIndex(layout)
	chosen = set()
	for _text, ids in items:
		chosen.update(i for i in ids if i in cells)
	if len({cells[i] for i in chosen}) < 2:
		return None  # a few words of one cell are copied as they are
	plain = []
	html = []
	done = set()
	for text, ids in items:
		inTable = [i for i in ids if i in cells]
		if ids and len(inTable) * 2 >= len(ids):
			for ti in sorted({cells[i][0] for i in inTable}, key=lambda t: min(c for c in inTable if cells[c][0] == t)):
				if ti in done:
					continue
				done.add(ti)
				t = layout["tables"][ti]
				plain.append(tableText(t, idx.words, chosen))
				html.append(tableHtml(t, idx.words, chosen))
			continue
		plain.append(text)
		html.append("<p>%s</p>" % _esc(text))
	return "\r\n".join(plain), "".join(html)


def documentHtml(idx, title, lang="ne"):
	"""The whole document as a web page: headings, paragraphs and real tables, page by page."""
	layout = getattr(idx, "layout", None) or {}
	cells = cellIndex(layout)
	heads = layout.get("heads") or {}
	wpage = layout.get("wpage") or []
	out = ['<!DOCTYPE html><html lang="%s"><head><meta charset="utf-8"><title>%s</title>' % (lang, _esc(title)),
		"<style>body{font-family:'Nirmala UI',Mangal,sans-serif;font-size:1.15em;max-width:60em;margin:1em auto;padding:0 1em;line-height:1.6}"
		"table{border-collapse:collapse;margin:1em 0}th,td{border:1px solid #777;padding:.3em .5em;vertical-align:top}"
		"th{background:#eef}section{border-top:1px dashed #aaa;margin-top:1.5em}</style></head><body>"]
	n = len(idx.words)
	pageStart = 0
	while pageStart < n:
		pn = wpage[pageStart] if pageStart < len(wpage) else 0
		end = pageStart
		while end < n and (wpage[end] if end < len(wpage) else 0) == pn:
			end += 1
		# (a table is shown where its first word is; its words on this page are all in it)
		out.append('<section aria-label="Page %d">' % (pn + 1))
		for piece in _lineGroups(idx, range(pageStart, end), cells):
			if piece[0] == "table":
				out.append(tableHtml(layout["tables"][piece[1]], idx.words))
				continue
			text = _esc(" ".join(_wordText(idx.words[i]) for i in piece[2]))
			level = heads.get(piece[1]) if piece[1] else None
			if level:
				out.append("<h%d>%s</h%d>" % (level, text, level))
			else:
				out.append("<p>%s</p>" % text)
		out.append("</section>")
		pageStart = end
	out.append("</body></html>")
	return "".join(out)


def cfHtml(fragment):
	"""The Windows clipboard's "HTML Format" for an HTML fragment (UTF-8 with byte offsets)."""
	pre = "<html><head><meta charset=\"utf-8\"></head><body><!--StartFragment-->"
	post = "<!--EndFragment--></body></html>"
	header = "Version:0.9\r\nStartHTML:%010d\r\nEndHTML:%010d\r\nStartFragment:%010d\r\nEndFragment:%010d\r\n"
	h0 = len((header % (0, 0, 0, 0)).encode("utf-8"))
	body = (pre + fragment + post).encode("utf-8")
	sf = h0 + len(pre.encode("utf-8"))
	ef = sf + len(fragment.encode("utf-8"))
	return (header % (h0, h0 + len(body), sf, ef)).encode("utf-8") + body
