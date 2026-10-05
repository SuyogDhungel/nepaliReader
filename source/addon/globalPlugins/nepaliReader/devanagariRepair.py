# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - repairs Unicode Devanagari text as PDF viewers extract it.
#
# Many Nepali/Hindi PDFs (InDesign, Word "save as PDF", iLovePDF ...) carry a broken text
# layer: the page looks right but the text NVDA receives is wrong. The rules below are based
# on the kinds of faults, not on particular words; every rule matches only sequences that
# cannot occur in correct Devanagari, so correct Unicode text passes through unchanged.
#
#   fault                                   example (extracted)   repaired
#   vowel signs repeated                    नााराायणीी            नारायणी
#   replacement / private-use characters    जि\ufffdल्ला            जिल्ला
#   stray Latin letters inside a word       प्राधिcकरण            प्राधिकरण
#   two vowel signs on one letter           रहेकाे                 रहेका
#   vowel sign or virama after a space      रहेकाे ा, घ ् टना       रहेका, घटना
#   virama after a vowel sign / doubled     विपद्का्, छन््          विपद्का, छन्
#   consonant repeated after reph           वर्गग                  वर्ग
#   anusvara / candrabindu repeated         साँँझ                  साँझ
#   ि before its consonant                  िशक्षा, ि शक्षा         शिक्षा
#   word split by a space                   कुु ल, जि ल्ला          कुल, जिल्ला
#     (joined only when the joined form is a dictionary word and the pieces are not)
#
# No NVDA dependencies.

import re
import unicodedata

try:
	from . import neLexicon
except ImportError:  # unit tests
	import neLexicon

_CONS = "\u0915-\u0939\u0958-\u095f"
_CLUSTER = "[" + _CONS + "]\u093c?(?:\u094d[" + _CONS + "]\u093c?)*"
_SIGNS = "\u093e-\u094c\u0962\u0963"   # dependent vowel signs
_MODS = "\u0900-\u0903"                # candrabindu, anusvara, visarga
_DEVA_LETTER = "\u0900-\u0963\u0971-\u097f"  # letters, signs (not digits, not danda)

_DEVANAGARI = re.compile("[\u0900-\u097f]")
_JUNK = re.compile("[\ufffd\u25cc\u00ad\ufeff\u200b\ue000-\uf8ff]")
# a non-Devanagari character glued between Devanagari letters: "प्राधिcकरण", "जोखि8म"
_GLUED = re.compile("(?<=[" + _DEVA_LETTER + "])[^\\s\u0900-\u097f\u200c\u200d।॥,.;:!?()\\[\\]{}'\"/\\-–—]{1,2}(?=[" + _DEVA_LETTER + "])")
# in map/table labels some fonts store ि as a digit or symbol: "गाउँपा)लका", "नाग2रक", "धा7दङ"
_GLUED_I = re.compile("(?<=[" + _DEVA_LETTER + "])[0-9)(*#@!%&+=<>?|\\^~]([" + _CONS + "]\u093c?)(?=[" + _DEVA_LETTER + "]|\\s|$)")
_SPACE_SIGN = re.compile(" [" + _SIGNS + _MODS + "\u094d]+")
_SAME_SIGN = re.compile("(?<=[" + _CONS + "\u093c" + _SIGNS + _MODS + "])([" + _SIGNS + "])\\1+")
_SIGN_RUN = re.compile("([" + _SIGNS + "])[" + _SIGNS + "]+")
# the same, but only where the signs follow a letter (signs alone stand for letters in Word PDFs)
_SIGN_RUN_AFTER = re.compile("(?<=[" + _CONS + "\u093c" + _MODS + "])([" + _SIGNS + "])[" + _SIGNS + "]+")
_MOD_RUN = re.compile("([" + _MODS + "])\\1+")
_HALANT_RUN = re.compile("\u094d\u094d+")
_SIGN_HALANT = re.compile("([" + _SIGNS + _MODS + "])\u094d")
_SPACED_HALANT = re.compile("(?<=\\S) \u094d ?(?=\\S)")
_DOUBLED = re.compile("([\u093e\u0940-\u094c\u0901\u0902])\\1|\ufffd| \u094d|[" + _SIGNS + "]\u094d")
_REPH_DOUBLE = re.compile("(\u0930\u094d([" + _CONS + "]))\\2(?![\u094d\u093c])")
_MISPLACED_I = re.compile("(^|[^" + _CONS + "\u093c\u094d\\s])\u093f(" + _CLUSTER + ")")
_DETACHED_I = re.compile("(^|\\s)\u093f\\s?(" + _CLUSTER + ")")
_ORPHAN = re.compile("(?<=[" + _CONS + _SIGNS + _MODS + "\u094d]) [" + _SIGNS + _MODS + "\u094d]+(?=\\s|$|[\u0964\u0965,.;:!?)\\]])")
_ORPHAN_BEFORE_WORD = re.compile("(?<=[" + _SIGNS + _MODS + "]) [" + _SIGNS + _MODS + "]+(?= )")
_TOKEN = re.compile("\\S+|\\s+")
_EDGE_PUNCT = "\u0964\u0965,.;:!?()[]{}'\"\u2018\u2019\u201c\u201d-\u2013\u2014/"
# a piece after a space that cannot begin a word
_CANNOT_START = re.compile("^(?:[" + _SIGNS + _MODS + "\u094d]|\u0930\u094d|([" + _CONS + "])\u094d\\1)")


def hasDevanagari(text):
	return bool(_DEVANAGARI.search(text))


def lowWordRate(text, minWords=60, rate=0.5):
	"""A Unicode text whose words are mostly not words at all (real text: 75-90% are words)."""
	k, n = wordStats(text)
	return n >= minWords and k < rate * n


def isBroken(text):
	"""Fault marks that never occur in correct text: doubled vowel signs, replacement characters,
	stray virama, symbols standing for ि. (A low share of real words is judged by the caller over
	a whole document, see wordStats.)"""
	return bool(_DOUBLED.search(text)) or bool(_GLUED_I.search(text))


def repairGain(text):
	"""(unknown words before, unknown words after a trial repair, words before).
	A damaged text layer loses many unknown words through repair; correct text almost none.
	Splitting is left out of the trial so long correct compounds do not count."""
	k0, n0 = wordStats(text)
	if n0 == 0:
		return 0, 0, 0
	global _noSplit
	_noSplit = True
	try:
		k1, n1 = wordStats(repair(text, broken=True))
	finally:
		_noSplit = False
	return n0 - k0, n1 - k1, n0


_noSplit = False


def wordStats(text):
	"""(dictionary words, Devanagari words) in `text`."""
	if not neLexicon.isLoaded():
		return 0, 0
	ws = [_core(w) for w in text.split()]
	ws = [w for w in ws if len(w) >= 2 and _DEVANAGARI.search(w)]
	return sum(1 for w in ws if neLexicon.isWord(w)), len(ws)


def _lowWordRate(text):
	if not neLexicon.isLoaded():
		return False
	ws = [_core(w) for w in text.split()]
	ws = [w for w in ws if len(w) >= 2 and _DEVANAGARI.search(w)]
	if len(ws) < 3:
		return False
	unknown = sum(1 for w in ws if not neLexicon.isWord(w))
	return unknown * 10 >= len(ws) * 4  # 40% or more are not words


def wordRate(text):
	"""Share of Devanagari words in `text` that are dictionary words (None if too few words)."""
	if not neLexicon.isLoaded():
		return None
	ws = [_core(w) for w in text.split()]
	ws = [w for w in ws if len(w) >= 2 and _DEVANAGARI.search(w)]
	if len(ws) < 3:
		return None
	return sum(1 for w in ws if neLexicon.isWord(w)) / float(len(ws))


def repair(text, broken=None):
	"""Repair `text`. `broken`: True when the document is already known to have a broken
	text layer (the caller remembers this per window); None = decide from this text."""
	if not _DEVANAGARI.search(text):
		return text
	if broken is None:
		broken = isBroken(text)
	text = _JUNK.sub("", text)
	if broken:
		text = _GLUED_I.sub(lambda m: m.group(1) + "\u093f", text)
	text = _GLUED.sub("", text)
	text = _SAME_SIGN.sub(r"\1", text)  # first, so a doubled ि is not taken for a misplaced one
	if broken:
		text = _SPACED_HALANT.sub("", text)  # "घ ् टना" -> "घटना"
	if not broken:
		text = _placeI(text)
	if broken:
		text = _REPH_DOUBLE.sub(r"\1", text)
	text = _SIGN_RUN_AFTER.sub(r"\1", text)
	text = _MOD_RUN.sub(r"\1", text)
	text = _SIGN_HALANT.sub(r"\1", text)
	text = _HALANT_RUN.sub("\u094d", text)
	if not broken:
		text = _ORPHAN.sub("", text)
		text = _ORPHAN_BEFORE_WORD.sub("", text)
	text = _SIGN_RUN_AFTER.sub(r"\1", text)
	text = unicodedata.normalize("NFC", text)
	if broken:
		text = _joinSplitWords(text)
		text = _REPH_DOUBLE.sub(r"\1", text)
		text = _SIGN_RUN_AFTER.sub(r"\1", text)
	return text


def _placeI(text):
	prev = None
	while prev != text:
		prev = text
		text = _MISPLACED_I.sub(lambda m: m.group(1) + m.group(2) + "\u093f", text)
		text = _DETACHED_I.sub(lambda m: m.group(1) + m.group(2) + "\u093f", text)
	return text


def _core(tok):
	return tok.strip(_EDGE_PUNCT)


def _known(word):
	return neLexicon.isLoaded() and neLexicon.isWord(word)


_fixCache = {}


_DIGITS = re.compile("[0-9\u0966-\u096f]")


def _fixWord(w):
	"""`w` itself if it is a word; else `w` with one repeated piece removed, if that is a word
	("गर्नुभर्नुयो" -> "गर्नुभयो", "सूचसूना" -> "सूचना"); else None."""
	if _DIGITS.search(w):
		return w if _known(w) else None  # numbers are never "repaired"
	if _known(w):
		return w
	if len(w) < 3 or len(w) > 30:
		return None
	if w in _fixCache:
		return _fixCache[w]
	found = None
	n = len(w)
	for L in (4, 3, 2, 1):
		for i in range(1, n - L + 1):
			piece = w[i:i + L]
			if piece in w[max(0, i - 8):i]:
				cand = w[:i] + w[i + L:]
				if _known(cand):
					found = cand
					break
		if found:
			break
	if len(_fixCache) > 20000:
		_fixCache.clear()
	_fixCache[w] = found
	return found


def _splitWord(w):
	"""Two words stuck together: "प्रधानमन्त्रीलेराष्ट्रिय" -> "प्रधानमन्त्रीले राष्ट्रिय"."""
	if len(w) < 6 or _noSplit:
		return None
	best = None
	for i in range(4, len(w) - 3):
		a, b = w[:i], w[i:]
		if b[0] in _SIGN_CHARS or a[-1] == "\u094d":
			continue
		if _known(a) and _known(b):
			if best is None or min(len(a), len(b)) > min(len(best[0]), len(best[1])):
				best = (a, b)
	return best and best[0] + " " + best[1]


_SIGN_CHARS = set(chr(c) for c in range(0x093E, 0x094E)) | {"\u0901", "\u0902", "\u0903", "\u093c"}
_DANDA_REPEAT = re.compile("^(\\S+?)([\u0964\u0965])(\\S+)$")


def _edges(tok):
	core = tok.strip(_EDGE_PUNCT)
	if not core:
		return "", tok, ""
	start = tok.index(core)
	return tok[:start], core, tok[start + len(core):]


JOIN_COST = 1.0
LENGTH_POWER = 1.4  # a word of n letters scores n ** LENGTH_POWER (longer real words win)


def _wscore(word):
	return len(word) ** LENGTH_POWER


def _groupWord(pieces):
	"""Text of pieces joined (no space), with outer punctuation kept apart. None if inner punctuation."""
	for k, p in enumerate(pieces):
		lead, core, trail = _edges(p)
		if not core or (k > 0 and lead) or (k < len(pieces) - 1 and trail):
			return None
	joined = "".join(pieces)
	return _edges(joined)


def _variants(pieces):
	"""Ways to read a group of pieces as one word: a piece that starts with a vowel sign either
	keeps it (the sign belongs to the letter before the space) or drops it (a repeated sign)."""
	outs = [""]
	for k, p in enumerate(pieces):
		lead, core, trail = _edges(p) if k == 0 else ("", p, "")
		if k > 0 and core and core[0] in _SIGN_CHARS:
			stripped = core.lstrip("".join(_SIGN_CHARS) + "\u094d")
			outs = [o + core for o in outs] + [o + stripped for o in outs]
		else:
			outs = [o + p for o in outs]
	return outs[:4]


_readCache = {}


def _readings(core, allowSwaps=True):
	"""Dictionary words this damaged piece could be; the longest wins (क्षति over क्षत)."""
	key = (core, allowSwaps)
	if key in _readCache:
		return _readCache[key]
	if len(_readCache) > 30000:
		_readCache.clear()
	r = _readingsUncached(core, allowSwaps)
	_readCache[key] = r
	return r


def _readingsUncached(core, allowSwaps):
	found = []
	seen = set()
	stripped = core.lstrip("".join(_SIGN_CHARS) + "\u094d")
	if _known(core):
		return core  # a real word is never changed
	decoded = _decodeWord(core) if _DOC_SWAPS else None
	if decoded:
		return decoded  # this document's own pattern explains the word
	for c in (core, _SIGN_RUN.sub(r"\1", _placeI(core)), stripped if stripped != core else ""):
		if c in seen or not c:
			continue
		seen.add(c)
		if _known(c):
			found.append(c)
			continue
		for f in (_fixWord(c), swapFix(c) if allowSwaps else None):
			if f:
				found.append(f)
	if not found:
		return None
	return max(found, key=len)


def _bestForm(pieces):
	"""(score, text) for one group of pieces read as one word."""
	g = _groupWord(pieces)
	if g is None:
		return None
	lead, core, trail = g
	if len(pieces) == 1 and all(ch in _SIGN_CHARS or ch == "\u094d" for ch in core):
		r = swapFix(core) if len(core) >= 2 else None
		if r:
			return (_wscore(r) - 1.0, lead + r + trail)  # "ििा" -> "वटा"
		return (-1.0, pieces[0])  # a vowel sign on its own: belongs to a neighbour
	penalty = JOIN_COST * (len(pieces) - 1)
	forced = len(pieces) > 1 and _CANNOT_START.match(_edges(pieces[1])[1] or " ")
	if forced:
		penalty = -0.5  # the second piece cannot begin a word: joining is certainly right
	best = None
	for v in (_variants(pieces) if len(pieces) > 1 else [core]):
		vl, vc, vt = _edges(v) if len(pieces) > 1 else (lead, v, trail)
		r = _readings(vc, allowSwaps=len(pieces) == 1 or bool(forced))
		if r and (best is None or len(r) > len(best[1])):
			best = (vl, r, vt)
	if best:
		return (_wscore(best[1]) - penalty, best[0] + best[1] + best[2])
	if len(pieces) == 1:
		split = _splitWord(core)
		if split:
			return (sum(_wscore(x) for x in split.split()) - 2.0, lead + split + trail)
		# not a known word: still apply the safe placement rules
		return (0.0, lead + _SIGN_RUN.sub(r"\1", _placeI(core)) + trail)
	if forced:
		v = _variants(pieces)[-1]
		return (0.0, _SIGN_RUN.sub(r"\1", _placeI(v)))
	return None


def _joinSplitWords(text):
	"""Dictionary-guided repair of one line. The line is cut into pieces at single spaces;
	the best grouping of pieces into words is chosen: dictionary words score their length,
	each join costs a little, so correct text (already real words) is left as it is.
	Inside a group, a repeated piece may be dropped and two stuck words may be split, but
	only when the result is a dictionary word."""
	toks = _TOKEN.findall(text)
	out = []
	i = 0
	while i < len(toks):
		# collect a run of Devanagari pieces separated by single spaces
		if toks[i].isspace() or not _DEVANAGARI.search(toks[i]):
			out.append(toks[i])
			i += 1
			continue
		run = [toks[i]]
		j = i + 1
		while j + 1 < len(toks) and toks[j] == " " and _DEVANAGARI.search(toks[j + 1]):
			run.append(toks[j + 1])
			j += 2
		out.append(_segment(run))
		i = j
	return "".join(out)


def _segment(pieces):
	pieces = [_DANDA_REPEAT.sub(lambda m: m.group(1) + m.group(2) if m.group(3).strip(_EDGE_PUNCT) and m.group(1).endswith(m.group(3).strip(_EDGE_PUNCT)) else m.group(0), p) for p in pieces]
	n = len(pieces)
	best = [(0.0, [])] + [None] * n
	for end in range(1, n + 1):
		for size in range(1, min(4, end) + 1):
			start = end - size
			if best[start] is None:
				continue
			form = _bestForm(pieces[start:end])
			if form is None:
				continue
			score = best[start][0] + form[0]
			if best[end] is None or score > best[end][0] + 1e-9:
				best[end] = (score, best[start][1] + [form[1]])
	if best[n] is None:
		return " ".join(pieces)
	return " ".join(best[n][1])


# ---------------------------------------------------------------------------
# Letter swaps of damaged PDFs (MS Word "Save as PDF" and others)
#
# Some PDF makers store, for each glyph on the page, a wrong character: the ि glyph comes out
# as त / ज / र, ट as ि, स् as ज, the reph as the letter under it (कार्य -> कायय), and so on.
# The swaps happen glyph by glyph in on-screen order, so candidates are made in on-screen
# order (ि before its letter, reph after it), turned back into Unicode order, and accepted
# only if the result is a dictionary word. The swap table (confusions.json) was learned by
# aligning PDF text with OCR of the same pages (tools/learn_confusions.py).
# ---------------------------------------------------------------------------

REPH_MARK = ""
_CLUSTER_RE = re.compile(_CLUSTER)
_CONFUSIONS = []


def loadConfusions(path=None):
	global _CONFUSIONS
	import json
	import os
	if path is None:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "confusions.json")
	try:
		with open(path, encoding="utf-8") as f:
			data = json.load(f)
	except (OSError, ValueError):
		_CONFUSIONS = []
		return 0
	pairs = []
	for key, count in data.items():
		src, _, dst = key.partition("\t")
		if src:
			pairs.append((src.replace("R", REPH_MARK), dst.replace("R", REPH_MARK), count))
	pairs.sort(key=lambda p: -p[2])
	_CONFUSIONS = pairs
	return len(pairs)


def toVisual(word):
	"""Unicode order -> on-screen order: ि before its consonant cluster, reph after its cluster."""
	out = []
	i = 0
	n = len(word)
	while i < n:
		reph = word.startswith("र्", i) and i + 2 < n and word[i + 2] in _CONS_SET
		start = i + 2 if reph else i
		m = _CLUSTER_RE.match(word, start) if start < n and word[start] in _CONS_SET else None
		if m:
			cl = m.group(0)
			end = m.end()
			if end < n and word[end] == "ि":
				out.append("ि" + cl)
				end += 1
			else:
				out.append(cl)
			if reph:
				out.append(REPH_MARK)
			i = end
		else:
			out.append(word[i])
			i += 1
	return "".join(out)


def fromVisual(text):
	"""On-screen order -> Unicode order (inverse of toVisual)."""
	out = []
	i = 0
	n = len(text)
	while i < n:
		ch = text[i]
		if ch == "ि" and i + 1 < n and text[i + 1] in _CONS_SET:
			m = _CLUSTER_RE.match(text, i + 1)
			out.append(m.group(0) + "ि")
			i = m.end()
			continue
		if ch == REPH_MARK:
			# attach र् before the cluster that precedes (skipping vowel signs)
			j = len(out) - 1
			while j >= 0 and all(c in _SIGNS_SET for c in out[j]):
				j -= 1
			if j >= 0:
				out[j] = "र्" + out[j]
			i += 1
			continue
		if ch in _CONS_SET:
			m = _CLUSTER_RE.match(text, i)
			out.append(m.group(0))
			i = m.end()
			continue
		out.append(ch)
		i += 1
	return "".join(out)


_CONS_SET = set(chr(c) for c in range(0x0915, 0x093A)) | set(chr(c) for c in range(0x0958, 0x0960))
_SIGNS_SET = set(chr(c) for c in range(0x093E, 0x094D)) | {"ँ", "ं", "ः", "ॢ", "ॣ"}
_swapCache = {}
# letters most often found stored as ि in Word-made PDFs (from the bulletin analysis)
_I_FOR = "\u091f\u0935\u0925\u0924\u0926\u0928\u0930\u0938\u0932\u0915\u092e\u092a\u092f\u0939\u0917\u092c\u091c\u091a\u0920\u0921"


def _structuralSwaps(w):
	"""Swaps that follow from how the glyphs are drawn: a consonant standing where a ि is drawn
	(right before another consonant) may be the ि; a doubled consonant may be consonant + reph."""
	pairs = []
	# a letter glyph stored as ि (Word PDFs: घिना = घटना, तिा = तथा, ििा = वटा)
	# ु drawn one letter too far right: "रामपरु" -> "रामपुर", "तबद्यतु" -> "बिद्युत"
	for k in range(len(w) - 2):
		if w[k] in _CONS_SET and w[k + 1] in _CONS_SET and w[k + 2] in "\u0941\u0942\u0943":
			pairs.append((w[k:k + 3], w[k] + w[k + 2] + w[k + 1], 0))
	for k in range(len(w) - 1):
		a, b = w[k], w[k + 1]
		if a in _CONS_SET and b in _CONS_SET and (k == 0 or w[k - 1] != "\u094d"):
			if a == b:
				pairs.append((a + b, a + REPH_MARK, 0))
			pairs.append((a + b, "\u093f" + b, 0))
	return pairs


def swapFix(word, maxSwaps=3):
	"""Correct a word damaged by letter swaps; None if no dictionary word is reached."""
	if not _CONFUSIONS or not neLexicon.isLoaded() or len(word) < 2 or len(word) > 25 or _DIGITS.search(word):
		return None
	if word in _swapCache:
		return _swapCache[word]
	found = None
	frontier = [word]
	seen = {word}
	for _depth in range(maxSwaps):
		nxt = []
		for w in frontier:
			for src, dst, _count in _DOC_SWAPS + ([] if len(_DOC_SWAPS) >= 5 else _CONFUSIONS) + _structuralSwaps(w):
				start = w.find(src)
				while start >= 0:
					cand = w[:start] + dst + w[start + len(src):]
					if cand not in seen:
						seen.add(cand)
						logical = unicodedata.normalize("NFC", fromVisual(cand))
						if logical and neLexicon.isWord(logical):
							found = logical
							break
						nxt.append(cand)
					start = w.find(src, start + 1)
				if found:
					break
			if found:
				break
		if found or len(seen) > 1500:
			break
		frontier = nxt[:150]
	if len(_swapCache) > 20000:
		_swapCache.clear()
	_swapCache[word] = found
	return found


# ---------------------------------------------------------------------------
# Learning one document's own pattern
#
# Each damaged PDF stores its own wrong characters (Word writes a different glyph table for each
# document and font). Before reading, the whole document's text is read once; for the words that
# are not dictionary words, every single-letter swap (in on-screen order) is tried, and the swaps
# that turn many DIFFERENT words of this document into dictionary words are taken as this
# document's pattern. They are then tried first, before the general table.
# ---------------------------------------------------------------------------

_DOC_SWAPS = []          # (src, dst, count) learned for the document being read
_docSwapKey = None
_SWAP_TARGETS = ["ि", "र्"[0:0] + REPH_MARK, "", "स्"] + \
	[chr(c) for c in range(0x0915, 0x093A)] + \
	["ा", "ी", "ु", "ू", "ृ", "े", "ै", "ो", "ौ", "ं", "ँ", "्"]


def _applyAll(w, swaps):
	"""Apply learned swaps all at once (like decoding a cipher: ग->ि and ि->ग together swap them).
	Uses the first (strongest) meaning of each stored piece."""
	cands = _decodings(w, swaps, limit=1)
	return cands[0] if cands else w


def _decodings(w, swaps, limit=48):
	"""All readings of `w` under the learned swaps, where a stored piece may have several meanings
	(in some PDFs ि stands for ग, ध and ख). Strongest meanings first."""
	if not swaps:
		return [w]
	table = {}
	for src, dst, _n in swaps:
		table.setdefault(src, [])
		if dst not in table[src]:
			table[src].append(dst)
	lens = sorted({len(k) for k in table}, reverse=True)
	parts = []
	i = 0
	n = len(w)
	while i < n:
		for L in lens:
			piece = w[i:i + L]
			if len(piece) == L and piece in table:
				parts.append(table[piece] + ([piece] if limit > 1 else []))
				i += L
				break
		else:
			parts.append([w[i]])
			i += 1
	out = [""]
	for opts in parts:
		out = [o + x for o in out for x in opts][: max(limit, 1) * 4]
	return out[:limit]


def _decodeWord(w):
	"""A dictionary word this damaged word stands for under this document's pattern, or None."""
	for cand in _decodings(w, _DOC_SWAPS):
		logical = unicodedata.normalize("NFC", fromVisual(cand))
		if logical != w and _known(logical):
			return logical
	return None


def learnDocumentSwaps(text, maxWords=300, minWords=5, rounds=12, timeLimit=60.0):
	"""Learn this document's letter swaps from its own text, in rounds: each round finds the
	swap (a stored piece of 1-3 characters -> a letter or sign) that turns the most DIFFERENT
	unknown words into dictionary words, given the swaps already learned."""
	import time
	if not neLexicon.isLoaded():
		return []
	start = time.monotonic()
	text = _basicClean(text)
	unknown = []
	seen = set()
	total = 0
	for tok in text.split():
		w = _core(tok)
		if len(w) < 3 or w in seen or _DIGITS.search(w) or not _DEVANAGARI.search(w) or not w.isprintable():
			continue
		seen.add(w)
		total += 1
		if not neLexicon.isWord(w):
			unknown.append(w)
		if len(unknown) >= maxWords:
			break
	learned = []

	def fixed(w):
		return neLexicon.isWord(unicodedata.normalize("NFC", fromVisual(w)))

	def explained(w):
		return any(fixed(c) for c in _decodings(w, learned, limit=24))

	for _round in range(rounds):
		if time.monotonic() - start > timeLimit:
			break
		pending = []
		for w in unknown:
			if not explained(w):
				pending.append(_applyAll(w, learned))
		counts = {}
		for v in pending:
			done = set()
			n = len(v)
			for i in range(n):
				for L in (1, 2, 3, 4, 5):
					if i + L > n:
						break
					src = v[i:i + L]
					if L > 3 and "\u094d" not in src:
						continue  # long pieces only for conjunct glyphs like ष्ट्र
					for dst in _SWAP_TARGETS:
						if dst == src:
							continue
						cand = v[:i] + dst + v[i + L:]
						if fixed(cand):
							key = (src, dst)
							if key not in done:
								done.add(key)
								counts[key] = counts.get(key, 0) + 1
			if time.monotonic() - start > timeLimit:
				break
		have = {(x[0], x[1]) for x in learned}
		meanings = {}
		for x in learned:
			meanings[x[0]] = meanings.get(x[0], 0) + 1
		counts = {k: v for k, v in counts.items() if k not in have and meanings.get(k[0], 0) < 3}
		if not counts:
			break
		(src, dst), n = max(counts.items(), key=lambda kv: (kv[1], -len(kv[0][0])))
		if n < minWords:
			break
		learned.append((src, dst, n))
	# keep the pattern only if, taken together, it explains a clear share of the unknown words
	if learned and unknown:
		good = sum(1 for w in unknown if explained(w))
		if good < 0.15 * len(unknown) or good < 10:
			return []
	return learned


def _basicClean(text):
	"""The safe, rule-only part of repair (no dictionary decisions), used before learning."""
	text = _JUNK.sub("", text)
	text = _SAME_SIGN.sub(r"\1", text)
	text = _SIGN_RUN_AFTER.sub(r"\1", text)
	text = _MOD_RUN.sub(r"\1", text)
	text = _SIGN_HALANT.sub(r"\1", text)
	text = _HALANT_RUN.sub("\u094d", text)
	return unicodedata.normalize("NFC", text)


def setDocumentSwaps(swaps, key):
	"""Use `swaps` (from learnDocumentSwaps) for the document identified by `key`."""
	global _DOC_SWAPS, _docSwapKey
	if key == _docSwapKey:
		return
	_DOC_SWAPS = list(swaps)
	_docSwapKey = key
	_swapCache.clear()
	_readCache.clear()
