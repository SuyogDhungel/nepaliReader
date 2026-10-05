# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - tells from screen pixels whether a line of text is drawn
# in Devanagari or in Latin letters.
#
# Preeti/Kruti Dev text is stored as English letters but drawn as Devanagari, so if
# the pixels show Devanagari while the text is ASCII, the text is a legacy font.
# Devanagari words have a continuous head line (shirorekha) across the top of each
# word; Latin text never has long horizontal ink runs in the upper part of the line.
# Pure Python on bytes (C-speed slicing), no numpy. No NVDA dependencies.

DEVANAGARI = "deva"
LATIN = "latin"


def _inkTable(bg, threshold):
	return bytes(1 if abs(v - bg) > threshold else 0 for v in range(256))


def classifyBgra(raw, width, height):
	"""Return DEVANAGARI, LATIN or None (blank / unreadable / blacked out) for one text line image."""
	if width < 8 or height < 6:
		return None
	raw = bytes(raw[:width * height * 4])
	green = raw[1::4]
	if len(green) < width * height:
		return None
	# background = most common green value (works for dark and light themes)
	counts = [0] * 256
	sample = green[::3]
	for v in set(sample):
		counts[v] = sample.count(v)
	bg = max(range(256), key=counts.__getitem__)
	if counts[bg] > 0.995 * len(sample):
		return None  # blank, or screen curtain
	table = _inkTable(bg, 70)
	ink = green.translate(table)
	rows = [ink[y * width:(y + 1) * width] for y in range(height)]
	rowCounts = [r.count(1) for r in rows]
	inkRows = [y for y, c in enumerate(rowCounts) if c > 0]
	if not inkRows:
		return None
	results = []
	# a rect may hold more than one line; split into bands of consecutive ink rows
	bands = []
	start = prev = inkRows[0]
	for y in inkRows[1:]:
		if y > prev + 1:
			bands.append((start, prev))
			start = y
		prev = y
	bands.append((start, prev))
	for top, bottom in bands:
		bandH = bottom - top + 1
		if bandH < 6:
			continue
		results.append(_classifyBand(rows[top:bottom + 1], width, bandH))
	results = [r for r in results if r]
	if not results:
		return None
	deva = results.count(DEVANAGARI)
	if deva * 2 >= len(results) and deva:
		return DEVANAGARI
	if LATIN in results:
		return LATIN
	return None


RUN_FACTOR = 0.85    # a head-line piece is at least this many band-heights long
DEVA_MIN = 0.45      # share of the line's ink columns covered by head-line pieces
LATIN_MAX = 0.12


def _classifyBand(rows, width, bandH):
	acc = 0
	for r in rows:
		acc |= int.from_bytes(r, "big")
	colInk = acc.to_bytes(width, "big")
	inkWidth = colInk.count(1)
	if inkWidth < bandH * 0.7:
		return None
	minRun = max(3, bandH * RUN_FACTOR)
	cover = []
	for r in rows:
		cover.append(sum(len(x) for x in r.split(b"\x00") if len(x) >= minRun) / float(inkWidth))
	# a filled block (selection highlight, box border, table rule) covers many rows
	if sum(1 for c in cover if c >= 0.6) > max(3, bandH * 0.3):
		return None
	best = max(cover[:max(2, int(bandH * 0.65))])
	if best >= DEVA_MIN and inkWidth >= bandH * 1.2:
		return DEVANAGARI
	if best <= LATIN_MAX and inkWidth >= bandH * 4:
		return LATIN
	return None
