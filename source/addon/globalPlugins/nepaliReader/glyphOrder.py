# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - signs a PDF viewer puts one letter too far to the right, words it
# glues together or cuts apart, and Preeti words inside Unicode lines.
# No NVDA dependencies.
#
# The pattern. A sign drawn over or under a letter (ु ू ृ ॄ े ै ं ँ ॅ) has no width of its own. Many
# viewers put the glyphs of a line in the order in which they start on the page, and such a sign
# starts where the next glyph starts, so it comes out after that glyph:
#     सेवा -> सवे ा      अनुसार -> अनसु ार      शुल्क -> शल्ुक      सक्नेछ -> सक्नछे
# The reph (र्) is drawn above the right end of its letter and comes out after that letter:
#     परिमार्जन -> परिमाजर्न      निर्णायक -> निणर्ायक
# Each key of a Preeti font is a glyph, so Preeti text inside the same PDF moves the same way:
#     शुल्क typed z'Ns comes out zN's,  बैंक typed a}+s comes out as+}
# The viewer also loses spaces where words meet (गरेअनुसारको) and puts one before a sign that
# follows a moved sign (सवे ा).
#
# A word is changed only into a word the dictionary or the word counts know. A word whose letters
# cannot be right as they stand (a sign after a halant, a sign at the start) is put back by the
# pattern the document has already shown, when the dictionary cannot decide.

import json
import math
import os
import re
import unicodedata
import zlib

# ---------------------------------------------------------------------------------------------
# letters and signs
# ---------------------------------------------------------------------------------------------
_CONS = set(chr(c) for c in list(range(0x0915, 0x093A)) + list(range(0x0958, 0x0960)) + list(range(0x0978, 0x0980)))
_INDEP = set(chr(c) for c in list(range(0x0904, 0x0915)) + [0x0960, 0x0961] + list(range(0x0972, 0x0978)))
NUKTA = "़"
VIRAMA = "्"
I_SIGN = "ि"
NASALS = "ँं"  # ँ ं
# drawn above or below a letter, with no width of their own
MARKS = set("ुूृॄॅेै") | set(NASALS)
# vowel signs that take room on the line
SPACING = set("ाीिोौॉॊः")
VOWEL_SIGNS = set("ािीुूृॄॅेैॉॊोौ")
_JOINERS = set("‌‍")
_DEVA_RE = re.compile("[ऀ-ॿ]")
_LETTER_RE = re.compile("[ऄ-हक़-ॡॲ-ॿ]")
REPH = "र्"
_EDGE = ".,;:!?()[]{}\"'‘’“”-–—।॥|/…*•"

# Case endings and postpositions written joined to a word (बैंकले, अनुसारको, कोडको)
SUFFIXES = tuple(sorted({
	"हरूको", "हरूका", "हरूकी", "हरूले", "हरूलाई", "हरूमा", "हरूबाट", "हरूसँग", "हरूद्वारा", "हरू",
	"हरुको", "हरुका", "हरुले", "हरुलाई", "हरुमा", "हरुबाट", "हरु",
	"को", "का", "की", "ले", "लाई", "मा", "बाट", "देखि", "सम्म", "सँग", "संग", "द्वारा", "भन्दा", "तिर",
	"भित्र", "बाहिर", "माथि", "मुनि", "पछि", "अघि", "नजिक", "बमोजिम", "अनुसार", "बापत", "वापत", "सरह",
	"जस्तो", "जस्तै", "मार्फत", "प्रति", "विरुद्ध", "स्थित", "मै", "कै", "नै", "पनि", "मात्र", "समेत",
	"मध्ये", "बीच", "बिच", "सहित", "रहित", "भरि", "भर",
}, key=len, reverse=True))
# endings that, standing alone after a word, belong to it (a font change cut बैंकले into बैंक ले)
CASE_ALONE = frozenset({"ले", "को", "का", "की", "मा", "लाई", "बाट", "हरू", "हरु", "हरूको", "हरूले", "हरूलाई", "हरूमा"})
# one-letter words that may stand alone
_ONE_LETTER_WORDS = frozenset({"र", "न", "त", "म", "ऊ", "ए", "ओ", "उ", "आ", "ई"})

# ---------------------------------------------------------------------------------------------
# word knowledge: the dictionary (neLexicon) and word counts from 350,000 sentences of news
# ---------------------------------------------------------------------------------------------
_FREQ = {}
_freqLoaded = [False]
_isWord = [None]  # neLexicon.isWord, set by setDictionary or loaded lazily
_autoLoad = [True]  # tests: load on first use; the add-on loads in its background thread


def loadFrequencies(path=None):
	if path is None:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nepaliFreq.dat")
	global _FREQ
	try:
		with open(path, "rb") as f:
			_FREQ = json.loads(zlib.decompress(f.read()).decode("utf-8"))
	except (OSError, ValueError, zlib.error):
		_FREQ = {}
	_freqLoaded[0] = True
	return len(_FREQ)


def setDictionary(isWord):
	_isWord[0] = isWord


def _lexicon(word):
	fn = _isWord[0]
	if fn is None:
		try:
			from . import neLexicon
		except ImportError:
			import neLexicon
		if not getattr(neLexicon, "_loaded", False):
			if not _autoLoad[0]:
				return False  # the add-on loads it in its background thread
			try:
				neLexicon.load()
			except Exception:
				return False
		fn = _isWord[0] = neLexicon.isWord
	try:
		return bool(fn(word))
	except Exception:
		return False


def setAutoLoad(on):
	"""The add-on loads the word counts in its background thread and turns this off, so a reading
	never waits for them."""
	_autoLoad[0] = on


def frequency(word):
	if not _freqLoaded[0] and _autoLoad[0]:
		loadFrequencies()
	return _FREQ.get(word, 0)


_knownCache = {}


def wordScore(word):
	"""How sure we are that `word` is a real word: 0 = unknown. Common words score higher."""
	s = _knownCache.get(word)
	if s is not None:
		return s
	s = _wordScore(word)
	if len(_knownCache) > 200000:
		_knownCache.clear()
	_knownCache[word] = s
	return s


def _wordScore(word):
	if not word or not _LETTER_RE.search(word):
		return 0.0
	f = frequency(word)
	if f >= 2:
		return 1.0 + math.log(f)
	if _lexicon(word):
		return 1.0
	# a known word with a case ending or postposition joined to it
	for suf in SUFFIXES:
		if len(word) > len(suf) + 1 and word.endswith(suf):
			stem = word[:-len(suf)]
			if not valid(stem):
				continue
			fs = frequency(stem)
			if fs >= 3 or _lexicon(stem):
				return 0.8 + 0.3 * math.log(fs + 1)
	return 0.0


def known(word):
	return wordScore(word) > 0


def solid(word):
	"""A known word that is not itself a common fault (the news text has निणर्य 85 times beside
	निर्णय): the old repairs leave such words alone."""
	if not known(word):
		return False
	if not valid(word):
		return False
	if _lexicon(word):
		return True
	r = _solidCache.get(word)
	if r is None:
		f = frequency(word)
		r = True
		for form, moves, kinds in candidates(word):
			if moves == 1 and "typed" not in kinds and frequency(form) >= max(_COMMON, 10 * f):
				r = False
				break
		if len(_solidCache) > 100000:
			_solidCache.clear()
		_solidCache[word] = r
	return r


_solidCache = {}
_total = [0]


def logProb(word):
	"""Log probability of `word` as a word of running Nepali text, or None when it is unknown.
	Rare dictionary words (no count in the news text) and words known only through a case
	ending get small probabilities, so a common word always beats them."""
	sc = wordScore(word)
	if sc <= 0:
		return None
	if not _total[0]:
		_total[0] = max(1, sum(_FREQ.values()))
	f = frequency(word)
	if f >= 2:
		return math.log(f / float(_total[0]))
	if sc >= 1.0:
		return math.log(0.5 / _total[0])
	return math.log(0.3 / _total[0])


# ---------------------------------------------------------------------------------------------
# glyph units ("atoms")
# ---------------------------------------------------------------------------------------------
# kinds: C consonant, H half consonant (with halant), V independent vowel, M mark over/under,
# S spacing sign (ा ी ो ौ ः), I the sign ि, D digit, O anything else


def atoms(word):
	out = []
	i = 0
	n = len(word)
	while i < n:
		ch = word[i]
		if ch in _CONS:
			j = i + 1
			if j < n and word[j] == NUKTA:
				j += 1
			if j < n and word[j] == VIRAMA:
				j += 1
				while j < n and word[j] in _JOINERS:
					j += 1
				out.append(["H", word[i:j]])
			else:
				out.append(["C", word[i:j]])
			i = j
			continue
		if ch in _JOINERS and out:
			out[-1][1] += ch
			i += 1
			continue
		if ch in _INDEP:
			kind = "V"
		elif ch in MARKS:
			kind = "M"
		elif ch == I_SIGN:
			kind = "I"
		elif ch in SPACING:
			kind = "S"
		elif "०" <= ch <= "९":
			kind = "D"
		elif ch == VIRAMA:
			kind = "X"  # a halant that follows no letter
		else:
			kind = "O"
		out.append([kind, ch])
		i += 1
	return out


def _join(ats):
	return "".join(t for _k, t in ats)


def valid(word):
	"""False for letter sequences that cannot occur in correctly written Nepali."""
	ats = atoms(word)
	if not ats:
		return False
	prev = None  # kind of the atom before; "N" after ं or ँ, "W" after a vowel sign
	for k, t in ats:
		if k == "X":
			return False
		if k in "MSI":
			if prev is None or prev in "HDOX":
				return False
			if t in VOWEL_SIGNS:
				if prev in "WNV":
					return False
				prev = "W"
			elif t in NASALS:
				if prev == "N":
					return False
				prev = "N"
			else:
				prev = "S"
			continue
		prev = k
	return True


def normalize(word):
	"""Signs of one letter in their usual order: vowel sign before ं / ँ."""
	word = re.sub("([ँं]+)([ा-ौॢॣ]+)", r"\2\1", word)
	return unicodedata.normalize("NFC", word)


_COMMON = 60  # a word seen this often in the news text is common

# ---------------------------------------------------------------------------------------------
# candidate forms of one word
# ---------------------------------------------------------------------------------------------
_MAX_OPPS = 5


def _opportunities(ats):
	"""Places where a sign or reph may have been moved: (kind, index, end)."""
	opps = []
	i = 0
	n = len(ats)
	while i < n:
		k, t = ats[i]
		if k == "M":
			j = i
			while j < n and ats[j][0] == "M":
				j += 1
			if i >= 2:
				opps.append(("mark", i, j))
			i = j
			continue
		if k == "H" and t.startswith(REPH) and i >= 1 and ats[i - 1][0] in "CSM":
			opps.append(("reph", i, i + 1))
		if k == "I" and (i == 0 or ats[i - 1][0] not in "CH") and i + 1 < n and ats[i + 1][0] in "CH":
			opps.append(("iBefore", i, i + 1))
		i += 1
	return opps


def _clusterStart(ats, end):
	"""Index where the consonant cluster ending at `end` (a C atom) starts (its half letters)."""
	s = end
	while s - 1 >= 0 and ats[s - 1][0] == "H" and not ats[s - 1][1].startswith(REPH):
		s -= 1
	return s


def _applyMark(ats, i, j, mode):
	"""Move the marks ats[i:j] back over the glyph before them. mode 1: one unit; 2: a whole cluster."""
	marks = ats[i:j]
	before = i - 1  # the glyph the marks were pushed past
	if mode == 1:
		target = before
	else:
		if ats[before][0] not in "CS":
			return None
		k = before
		if ats[k][0] == "S":
			k -= 1
		if k < 0 or ats[k][0] != "C":
			return None
		target = _clusterStart(ats, k)
		if target == before:
			return None
	if target < 1:
		return None
	base = ats[target - 1]
	if any(t in VOWEL_SIGNS for _k, t in marks):
		if base[0] != "C":
			return None
	elif not (base[0] in "CVS" or (base[0] == "M" and base[1] in VOWEL_SIGNS)):
		return None
	return ats[:target] + marks + ats[target:i] + ats[j:]


def _applyReph(ats, i, mode):
	"""Move a reph found after its letter (and that letter's signs) back before it.
	mode 1: before the letter; 2: before its whole cluster."""
	k = i - 1
	while k >= 0 and ats[k][0] in "SM":
		k -= 1
	if k < 0 or ats[k][0] != "C":
		return None
	target = k if mode == 1 else _clusterStart(ats, k)
	if mode == 2 and target == k:
		return None
	return ats[:target] + [ats[i]] + ats[target:i] + ats[i + 1:]


def _applyI(ats, i):
	"""A ि drawn before its letter (on-screen order) goes after the letter's cluster."""
	k = i + 1
	while k < len(ats) and ats[k][0] == "H":
		k += 1
	if k >= len(ats) or ats[k][0] != "C":
		return None
	return ats[:i] + ats[i + 1:k + 1] + [ats[i]] + ats[k + 1:]


def candidates(word, limit=300):
	"""Forms of `word` with some of its moved signs put back: [(form, moves, kinds)]."""
	ats = atoms(word)
	opps = _opportunities(ats)
	results = {}
	if opps:
		if len(opps) > _MAX_OPPS:
			# the places that cannot be right as they stand first, then from the left
			bad = [o for o in opps if not _okAsIs(ats, o)]
			rest = [o for o in opps if o not in bad]
			opps = (bad + rest)[:_MAX_OPPS]
		# from the left: a move to the left leaves every later index where it was
		opps.sort(key=lambda o: o[1])
	else:
		opps = []

	def walk(idx, cur, moves, kinds):
		if len(results) >= limit:
			return
		if idx == len(opps):
			if moves:
				form = normalize(_join(cur))
				if form != word and (form not in results or results[form][0] > moves):
					results[form] = (moves, tuple(kinds))
			return
		walk(idx + 1, cur, moves, kinds)
		kind, i, j = opps[idx]
		if kind == "mark":
			# all the signs of the run were pushed, or only the first few (हनुे: ु was, े was not)
			for cut in range(j, i, -1):
				for mode in (1, 2):
					nxt = _applyMark(cur, i, cut, mode)
					if nxt is not None:
						walk(idx + 1, nxt, moves + 1, kinds + ["mark" if mode == 1 else "markCluster"])
		elif kind == "reph":
			for mode in (1, 2):
				nxt = _applyReph(cur, i, mode)
				if nxt is not None:
					walk(idx + 1, nxt, moves + 1, kinds + ["reph"])
		elif kind == "iBefore":
			nxt = _applyI(cur, i)
			if nxt is not None:
				walk(idx + 1, nxt, moves + 1, kinds + ["iBefore"])

	walk(0, ats, 0, [])
	# typing faults that look like moved signs (काे, भयोे, सयाँै): put together or drop the extra sign
	for form, kinds in _typedForms(word):
		if form != word and form not in results:
			results[form] = (1, tuple(kinds))
	return [(f, m, k) for f, (m, k) in results.items()]


_COMPOSE = (("\u093e\u0947", "\u094b"), ("\u093e\u0948", "\u094c"), ("\u0947\u093e", "\u094b"), ("\u0948\u093e", "\u094c"),
	("\u094b\u0947", "\u094b"), ("\u0947\u0947", "\u0947"), ("\u0948\u0948", "\u0948"), ("\u0941\u0941", "\u0941"),
	("\u094b\u093e", "\u094b"), ("\u0902\u0902", "\u0902"), ("\u0901\u0901", "\u0901"),
	# a sign drawn twice for a bold look (fake bold): सिर्जिित, कुुदुु
	("\u093f\u093f", "\u093f"), ("\u0940\u0940", "\u0940"), ("\u0942\u0942", "\u0942"), ("\u0943\u0943", "\u0943"),
	("\u094b\u094b", "\u094b"), ("\u094c\u094c", "\u094c"))
# the letter under a reph written twice (रेकर्डड, दुर्गगम, सम्पूर्णण)
_REPH_TWICE = re.compile("(\u0930\u094d)([\u0915-\u0939]\u093c?)\\2")
_NASAL_FIRST = re.compile("([\u0901\u0902])([\u093e-\u094c]+)")


def _typedForms(word):
	out = []
	w = word
	for a, b in _COMPOSE:
		w = w.replace(a, b)
	w = _NASAL_FIRST.sub(r"\2\1", w)
	w = _REPH_TWICE.sub(r"\1\2", w)
	# ा + ँ + ै typed for ौँ
	w = w.replace("\u093e\u0901\u0948", "\u094c\u0901").replace("\u093e\u0902\u0948", "\u094c\u0902")
	w = unicodedata.normalize("NFC", w)
	if w != word:
		out.append((w, ["typed"]))
	return out


def _okAsIs(ats, opp):
	kind, i, j = opp
	if kind == "mark":
		return ats[i - 1][0] in "CVS" and not (ats[i - 1][0] == "S" and any(t in VOWEL_SIGNS for _k, t in ats[i:j]))
	if kind == "iBefore":
		return False
	return True


# ---------------------------------------------------------------------------------------------
# the document's own pattern
# ---------------------------------------------------------------------------------------------
class Pattern:
	"""What one document has shown: how often each kind of move made a real word."""

	def __init__(self):
		self.counts = {}
		self.fixedWords = 0

	def note(self, kinds):
		"""Moves that made a known word. A forced fix (no dictionary proof) teaches nothing."""
		if "forced" in kinds:
			return
		for k in kinds:
			self.counts[k] = self.counts.get(k, 0) + 1
		self.fixedWords += 1

	def shows(self, kind, least=3):
		n = self.counts.get(kind, 0)
		if kind in ("mark", "markCluster", "markFirst"):
			n = self.counts.get("mark", 0) + self.counts.get("markCluster", 0) + self.counts.get("markFirst", 0)
		return n >= least

	def summary(self):
		return dict(self.counts)


_PATTERNS = {}


def patternFor(key):
	p = _PATTERNS.get(key)
	if p is None:
		if len(_PATTERNS) > 60:
			_PATTERNS.clear()
		p = _PATTERNS[key] = Pattern()
	return p


# ---------------------------------------------------------------------------------------------
# one word
# ---------------------------------------------------------------------------------------------
_fixCache = {}


def fixWord(word, pattern=None, typed=False, allowValid=False, force=True):
	"""The right form of one word (no punctuation) and the moves that made it, or None.
	A word whose letters cannot be right as they stand is always looked at. A word that could
	be right (only unknown to the dictionary) is changed only with allowValid, that is when the
	document or the line has shown the pattern. typed: text people typed (web pages, Word): only
	a word that cannot be right is changed, and only into a known word."""
	key = (word, typed, allowValid, force, pattern is not None and pattern.shows("mark"), pattern is not None and pattern.shows("reph"))
	if key in _fixCache:
		return _fixCache[key]
	res = _fixWord(word, pattern, typed, allowValid, force)
	if len(_fixCache) > 100000:
		_fixCache.clear()
	_fixCache[key] = res
	return res


def _forcedOk(kinds):
	return all(k in ("mark", "markCluster", "reph") for k in kinds)


def _fixWord(word, pattern, typed, allowValid, force=True):
	if not word or not _DEVA_RE.search(word):
		return None
	ok = valid(word)
	if ok and known(word):
		# the news text has this very fault too (निणर्य 85 times): a word seen far less often than
		# the same word with one sign put back is taken for the fault, where the pattern shows
		if typed or not allowValid or _lexicon(word):
			return None
		f = frequency(word)
		for form, moves, kinds in candidates(word):
			if moves == 1 and "typed" not in kinds and valid(form) and frequency(form) >= max(_COMMON, 10 * f):
				return form, kinds
		return None
	if ok and typed:
		return None
	if ok and not allowValid:
		# no other sign of the pattern: only one move that gives a common word
		for form, moves, kinds in candidates(word):
			if moves == 1 and "typed" not in kinds and valid(form) and frequency(form) >= _COMMON:
				break
		else:
			return None
	cands = candidates(word)
	if not cands:
		return None
	best = None
	for form, moves, kinds in cands:
		if not valid(form):
			continue
		if ok and not allowValid and (moves != 1 or frequency(form) < _COMMON):
			continue
		lp = logProb(form)
		if lp is None:
			continue
		score = lp - 1.0 * moves
		if pattern is not None and all(pattern.shows(k) for k in kinds):
			score += 0.5
		if best is None or score > best[0]:
			best = (score, form, kinds)
	if best is not None:
		return best[1], best[2]
	if ok or typed or not force:
		return None
	# letters that cannot be right: put back by the move the document has shown (or by the most
	# common move, one unit to the left) even when the result is not in the dictionary (names)
	order = []
	for form, moves, kinds in cands:
		if valid(form) and (_forcedOk(kinds) or all(k == "typed" for k in kinds)):
			typedFix = all(k == "typed" for k in kinds)
			follows = pattern is not None and all(pattern.shows(k) for k in kinds)
			order.append((0 if typedFix else 1, 0 if follows else 1, moves, 0 if all(k in ("mark", "reph") for k in kinds) else 1, form, kinds))
	if not order:
		return None
	order.sort()
	return order[0][4], ("forced",) + tuple(order[0][5])


# ---------------------------------------------------------------------------------------------
# words glued together
# ---------------------------------------------------------------------------------------------
def _partForm(part, pattern, moves=True, ending=False):
	"""(score, form, kinds) for a piece of a glued word, or None when it is no word.
	ending: the piece may be a case ending (it opens the run and a word comes before it)."""
	if not part:
		return None
	if part in CASE_ALONE:
		return (math.log(1e-3), part, ()) if ending else None
	if len(part) == 1 and part not in _ONE_LETTER_WORDS:
		return None
	if valid(part):
		lp = logProb(part)
		if lp is not None:
			return lp, part, ()
	if not moves:
		return None
	fx = _fixWord(part, pattern, False, True, False)
	if fx is None:
		return None
	lp = logProb(fx[0])
	if lp is None:
		return None
	return lp - 1.0 * len(fx[1]), fx[0], fx[1]


def splitGlued(word, pattern=None, maxParts=3, moves=True, afterWord=False):
	"""Two or three known words for one unknown run of letters, or None. moves: the pieces may
	have moved signs put back too."""
	ats = atoms(word)
	n = len(ats)
	if n < 4 or n > 40:
		return None
	# cut only before a letter or an independent vowel (never before a sign)
	cuts = [i for i in range(1 if afterWord else 2, n - 1) if ats[i][0] in "CHV"]
	memo = {}

	def best(start, partsLeft):
		key = (start, partsLeft)
		if key in memo:
			return memo[key]
		res = None
		whole = _partForm(_join(ats[start:]), pattern, moves)
		if whole is not None:
			res = (whole[0], [whole[1]], list(whole[2]))
		if partsLeft > 1:
			for c in cuts:
				if c <= start or (c == start + 1 and not (afterWord and start == 0)) or c > start + 20:
					continue
				left = _partForm(_join(ats[start:c]), pattern, moves, ending=afterWord and start == 0)
				if left is None:
					continue
				right = best(c, partsLeft - 1)
				if right is None:
					continue
				score = left[0] + right[0] - 1.0
				if res is None or score > res[0]:
					res = (score, [left[1]] + right[1], list(left[2]) + right[2])
		memo[key] = res
		return res

	r = best(0, maxParts)
	if r is None or len(r[1]) < 2:
		return None
	return r[1], r[2]


# ---------------------------------------------------------------------------------------------
# Preeti words inside a Unicode line
# ---------------------------------------------------------------------------------------------
_PREETI_KEYS = set("+}{][\\|'\";/`~=^&*()_<>%$#@!?.,:")
_ASCII_WORD = re.compile(r"^[!-~]+$")
_NUMBERISH = re.compile(r"^[\d.,:/%\-+()]+$")
_URLISH = re.compile(r"(://|www\.|@.+\.|\.(com|org|np|gov|net|edu|pdf|docx?)\b)", re.I)
_ACRONYM = re.compile(r"^[A-Z]{2,8}s?$")
_COMMON_LATIN = frozenset({
	"rs", "no", "km", "kg", "mm", "cm", "ft", "etc", "vs", "eg", "ie", "dr", "mr", "mrs", "ms", "st",
	"pvt", "ltd", "inc", "co", "am", "pm", "ok", "id", "tv", "fm", "gm", "ml", "sq", "kw", "mw",
})
_englishWord = [None]
_swapReading = [None]


def setSwapReading(fn):
	"""fn(word) -> a known word the letter-swap repair makes of `word`, or None. A word that is one
	known word with letters swapped (बालबाललका for बालबालिका) is not split."""
	_swapReading[0] = fn


def _swapWord(core):
	fn = _swapReading[0]
	if fn is None:
		return None
	try:
		r = fn(core)
	except Exception:
		return None
	return r if r and r != core and " " not in r else None


def setEnglishCheck(fn):
	_englishWord[0] = fn


def _isEnglish(tok):
	fn = _englishWord[0]
	if fn is None:
		try:
			try:
				from . import detector
			except ImportError:
				import detector
			fn = _englishWord[0] = detector.isEnglishWord
		except Exception:
			fn = None
	low = tok.lower().strip("'\".,;:()[]")
	if low in _COMMON_LATIN:
		return True
	if fn is None:
		return False
	try:
		return bool(fn(low))
	except Exception:
		return False


def _preetiConverter(tok):
	try:
		from . import legacyFonts
	except ImportError:
		import legacyFonts
	return legacyFonts.convert(tok, "preeti")


def preetiToken(tok, convert, pattern=None, proofOnly=False):
	"""The Devanagari a Preeti word inside a Unicode line stands for, or None to leave it."""
	if not tok or not _ASCII_WORD.match(tok) or not re.search("[A-Za-z]", tok):
		return None
	if _NUMBERISH.match(tok) or _URLISH.search(tok):
		return None
	core = tok.strip(".,;:!?\"'()[]")
	if not core:
		return None
	if _ACRONYM.match(core):
		return None
	keys = sum(1 for ch in tok if ch in _PREETI_KEYS and ch not in ".,:!?")
	inner = any(ch in _PREETI_KEYS for ch in core[1:-1]) or any(ch in "+}{][\\|';" for ch in core)
	if _isEnglish(core) and not inner:
		return None
	try:
		conv = convert(tok)
	except Exception:
		return None
	if not conv or not _DEVA_RE.search(conv) or re.search("[A-Za-z]", conv):
		return None
	words = conv.split()
	out = []
	kinds = []
	for w in words:
		lead = len(w) - len(w.lstrip(_EDGE))
		trail = len(w) - len(w.rstrip(_EDGE))
		body = w[lead:len(w) - trail] if trail else w[lead:]
		form = body
		if body:
			# Preeti keys moved by the viewer: put back whenever the result is a known word
			fx = fixWord(body, pattern, allowValid=True)
			if fx is not None:
				form = fx[0]
				kinds.extend(fx[1])
		out.append((w[:lead], form, w[len(w) - trail:] if trail else ""))
	bodies = [f for _l, f, _t in out if f]
	if not bodies:
		return None
	text = " ".join(l + f + t for l, f, t in out)
	if all(wordScore(b) >= 1.0 for b in bodies):
		return text, kinds
	# no dictionary proof: only with Preeti keys inside the word and letters that can be right
	if not proofOnly and inner and keys >= 1 and len(core) >= 3 and all(valid(b) for b in bodies):
		return text, kinds
	return None


# ---------------------------------------------------------------------------------------------
# one line
# ---------------------------------------------------------------------------------------------
def _split(tok):
	lead = len(tok) - len(tok.lstrip(_EDGE))
	rest = tok[lead:]
	core = rest.rstrip(_EDGE)
	return tok[:lead], core, rest[len(core):]


def _devaShare(text):
	deva = len(re.findall("[ऄ-हक़-ॡ]", text))
	latin = len(re.findall("[A-Za-z]", text))
	return deva / float(deva + latin) if deva + latin else 0.0


def copiedFromPdf(text):
	"""True when typed text shows the PDF pattern at least twice: words that cannot be right and
	turn into known words with their signs put back, or a sign cut off from its word (सवे ा)."""
	n = 0
	toks = text.split()
	for i, t in enumerate(toks):
		lead, core, trail = _split(t)
		if not core or not _DEVA_RE.search(core):
			continue
		if i and core[0] in (MARKS | SPACING) - {I_SIGN} and _DEVA_RE.search(toks[i - 1][-1:]) and _LETTER_RE.search(toks[i - 1]):
			n += 1
		elif not valid(core):
			fx = fixWord(core, None, typed=True)
			if fx is not None and any(k in ("mark", "markCluster", "reph") for k in fx[1]):
				n += 1
		if n >= 2:
			return True
	return False


def fixLine(text, pattern=None, typed=False, convertPreeti=None, markExact=None):
	"""The line with moved signs put back. typed: see fixWord (no joining, splitting or Preeti).
	convertPreeti: a function that turns Preeti keys into Devanagari, for Preeti words found
	inside a Unicode line. markExact: called with the words this function settled."""
	if not text or not _DEVA_RE.search(text):
		return text
	proofOnly = False
	if typed and copiedFromPdf(text):
		# typed text (a web page, Word) that was copied out of a PDF with the damage in it
		typed = False
		proofOnly = True
		if convertPreeti is not None:
			convertPreeti = convertPreeti or True
	toks = re.split(r"(\s+)", text)
	changed = False
	settled = []
	evidence = 0  # signs of the pattern in this line
	joined = set()  # indexes of words a cut-off sign was given back to
	# 1. Preeti words inside a line that is mostly Unicode Devanagari
	if convertPreeti is True:
		convertPreeti = _preetiConverter
	if convertPreeti and not typed and _devaShare(text) >= 0.6:
		for i, t in enumerate(toks):
			if not t or t.isspace() or _DEVA_RE.search(t):
				continue
			res = preetiToken(t, convertPreeti, pattern, proofOnly)
			if res is not None and res[0] != t:
				toks[i] = res[0]
				changed = True
				settled.append(res[0])
				if res[1]:
					evidence += 1
				if pattern is not None:
					pattern.note(list(res[1]) + ["preeti"])
	if not typed:
		# 2. a sign cut off from its word by a space goes back to it (not ि, which is drawn
		# before its letter)
		i = 2
		while i < len(toks):
			t = toks[i]
			prev = toks[i - 2]
			if (t and t[0] in (MARKS | SPACING | {VIRAMA}) - {I_SIGN} and toks[i - 1] == " " and prev
					and _DEVA_RE.match(prev[-1]) and prev[-1] not in "।॥" and _LETTER_RE.search(prev)):
				# only where the joined word is a word, or becomes one with its signs put back
				# (सवे ा -> सेवा); a sign left over from a lost letter (संसदले ो for यो) stays
				plead, pcore, ptrail = _split(prev)
				tlead, tcore, ttrail = _split(t)
				whole = pcore + ptrail + tlead + tcore
				proof = known(whole) and valid(whole)
				if not proof:
					# the space came with a moved sign, so the word must need a sign put back
					fx = fixWord(whole, pattern, allowValid=True, force=False)
					proof = fx is not None and any(k in ("mark", "markCluster", "reph") for k in fx[1])
					if not proof and len(whole) >= 4:
						sp = splitGlued(whole, pattern)
						proof = sp is not None and any(k in ("mark", "markCluster", "reph") for k in sp[1]) and sp[0][0] != _split(prev)[1]
				if proof and not ptrail and not tlead:
					toks[i - 2] = toks[i - 2] + t
					del toks[i - 1:i + 1]
					joined.add(i - 2)
					changed = True
					evidence += 1
					continue
			i += 1
		# 3. a lone letter that repeats the end of the word before it (a glyph drawn twice)
		i = 2
		while i < len(toks):
			t = toks[i]
			lead, core, trail = _split(t) if t and not t.isspace() else ("", "", "")
			if core and len(core) == 1 and core in _CONS and core not in _ONE_LETTER_WORDS and toks[i - 1] == " ":
				prev = toks[i - 2]
				plead, pcore, ptrail = _split(prev)
				if pcore and pcore.endswith(core) and not ptrail:
					toks[i - 2] = prev + lead + trail
					del toks[i - 1:i + 1]
					changed = True
					continue
			i += 1
	# 4. words whose letters cannot be right as they stand and that the dictionary shows were
	# moved (other damage, such as letters a PDF swapped, is not this pattern)
	words = {}
	for i, t in enumerate(toks):
		if not t or t.isspace() or not _DEVA_RE.search(t):
			continue
		lead, core, trail = _split(t)
		if core:
			words[i] = (lead, core, trail)
			if not valid(core):
				fx = fixWord(core, pattern, allowValid=True, force=False)
				if fx is not None and any(k in ("mark", "markCluster", "reph") for k in fx[1]):
					evidence += 1
	shown = pattern is not None and (pattern.shows("mark") or pattern.shows("reph"))
	allow = not typed and (evidence > 0 or shown)
	done = {}
	for i, (lead, core, trail) in words.items():
		fx = fixWord(core, pattern, typed, allowValid=allow or i in joined, force=False)
		if fx is not None:
			done[i] = (lead + fx[0] + trail, [fx[0]], fx[1])
	# 5. words the viewer glued together
	if not typed and (allow or joined):
		for i, (lead, core, trail) in words.items():
			if i in done or (valid(core) and known(core)) or len(core) < 4:
				continue
			prev = toks[i - 2] if i >= 2 and toks[i - 1] == " " else ""
			afterWord = bool(prev) and bool(_DEVA_RE.search(prev[-1:])) and not lead
			if not (allow or i in joined):
				continue
			if i not in joined and _swapWord(core):
				continue  # one word with letters swapped: for the letter-swap repair
			sp = splitGlued(core, pattern, moves=True, afterWord=afterWord)
			if sp is not None:
				done[i] = (lead + " ".join(sp[0]) + trail, sp[0], list(sp[1]) + ["split"])
	# 6. what is left and cannot be right as it stands: the most likely move, where the line or
	# the document shows the pattern (a word drawn twice over is for the other repairs)
	if allow:
		for i, (lead, core, trail) in words.items():
			if i in done or valid(core):
				continue
			fx = fixWord(core, pattern, typed, allowValid=True, force=True)
			if fx is not None:
				done[i] = (lead + fx[0] + trail, [], fx[1])
	for i, (form, parts, kinds) in done.items():
		toks[i] = form
		# only real words are final; the other repairs may still work on the rest
		settled.extend(w for w in parts if known(w))
		if pattern is not None:
			pattern.note(kinds)
		changed = True
	if not changed:
		return text
	res = "".join(toks)
	if not typed:
		# 7. an ending left on its own (a font change cut बैंकले into बैंक ले) goes back to its word
		res = re.sub("(?<=[\u0900-\u0963\u0971-\u097f]) (" + "|".join(sorted(CASE_ALONE, key=len, reverse=True)) + ")(?=[\\s,।॥;:!?)]|$)",
			lambda m: m.group(1), res)
	if markExact is not None and settled:
		try:
			markExact(" ".join(settled))
		except Exception:
			pass
	return res
