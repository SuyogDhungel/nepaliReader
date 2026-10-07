# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - legacy (non-Unicode) Devanagari font converters.
# This module has no NVDA dependencies so it can be unit tested on its own.
#
# Supported encodings:
#   Nepali: Preeti, Kantipur, Sagarmatha, Fontasy Himali, PCS Nepali
#   Hindi:  Kruti Dev (010 and the common Kruti Dev family layout)
#
# The Kruti Dev rules are a port of kru2uni / @anthro-ai/krutidev-unicode (ISC licence).
# The Preeti-family character tables were cross-checked against npttf2utf.

import re
import unicodedata

# ---------------------------------------------------------------------------
# Unicode helpers
# ---------------------------------------------------------------------------

HALANT = "्"
NUKTA = "़"
I_SIGN = "ि"  # ि
CONSONANTS = set(chr(c) for c in range(0x0915, 0x093A)) | set(chr(c) for c in range(0x0958, 0x0960))
# dependent vowel signs and modifiers that can trail a consonant cluster
SIGNS = set("ािीुूृॄॅॆेैॉॊोौँंः")
MATRAS = set("ािीुूृॄॅॆेैॉॊोौ")
NASALS = set("ँं")

# Private-use markers used while converting
_I = ""     # ि typed before its consonant
_REPH = ""  # reph (र्) typed after its syllable
_MOD = ""   # Preeti 'm' modifier (प->फ, उ->ऊ, भ->झ, त्र->क्र, त्त->क्त)


def _clusterStart(s, end):
	"""Given index `end` of the last consonant of a cluster, return the index of its first consonant."""
	i = end
	if i > 0 and s[i] == NUKTA:
		i -= 1
	while i >= 2 and s[i - 1] == HALANT and (s[i - 2] in CONSONANTS or s[i - 2] == NUKTA):
		i -= 2
		if s[i] == NUKTA and i > 0:
			i -= 1
	return i


def _clusterEnd(s, start):
	"""Given index `start` of a consonant, return index just past the full conjunct cluster."""
	i = start + 1
	n = len(s)
	if i < n and s[i] == NUKTA:
		i += 1
	while i + 1 < n and s[i] == HALANT and s[i + 1] in CONSONANTS:
		i += 2
		if i < n and s[i] == NUKTA:
			i += 1
	return i


# ---------------------------------------------------------------------------
# Preeti family
# ---------------------------------------------------------------------------

PREETI_MAP = {
	# number row (unshifted keys give letters in Preeti; shifted give digits)
	"`": "ञ", "1": "ज्ञ", "2": "द्द", "3": "घ", "4": "द्ध", "5": "छ", "6": "ट", "7": "ठ",
	"8": "ड", "9": "ढ", "0": "ण्", "-": "(", "=": ".",
	"~": "ञ्", "!": "१", "@": "२", "#": "३", "$": "४", "%": "५", "^": "६", "&": "७",
	"*": "८", "(": "९", ")": "०", "_": ")", "+": "ं",
	# top row
	"q": "त्र", "w": "ध", "e": "भ", "r": "च", "t": "त", "y": "थ", "u": "ग", "i": "ष्",
	"o": "य", "p": "उ", "[": "ृ", "]": "े", "\\": HALANT,
	"Q": "त्त", "W": "ध्", "E": "भ्", "R": "च्", "T": "त्", "Y": "थ्", "U": "ग्", "I": "क्ष्",
	"O": "इ", "P": "ए", "{": _REPH, "}": "ै", "|": "्र",
	# home row
	"a": "ब", "s": "क", "d": "म", "f": "ा", "g": "न", "h": "ज", "j": "व", "k": "प",
	"l": _I, ";": "स", "'": "ु",
	"A": "ब्", "S": "क्", "D": "म्", "F": "ँ", "G": "न्", "H": "ज्", "J": "व्", "K": "प्",
	"L": "ी", ":": "स्", '"': "ू",
	# bottom row
	"z": "श", "x": "ह", "c": "अ", "v": "ख", "b": "द", "n": "ल", "m": _MOD,
	",": ",", ".": "।", "/": "र",
	"Z": "श्", "X": "ह्", "C": "ऋ", "V": "ख्", "B": "द्य", "N": "ल्", "M": "ः",
	"<": "?", ">": "श्र", "?": "रु",
	# extended (Alt / Windows-1252) characters
	"„": "ध्र", "…": "‘", "ˆ": "फ्", "‰": "झ्", "‹": "ङ्घ",
	"‘": "ॅ", "“": "ँ", "Œ": "त्त्", "•": "•", "˜": "ऽ", "›": "द्र", "\xa1": "ज्ञ्",
	"\xa2": "द्घ", "\xa3": "घ्", "\xa4": "झ्", "\xa5": "र्‍", "\xa7": "ट्ट", "\xa9": "र",
	"\xaa": "ङ", "\xab": "्र", "\xac": "ु", "\xb0": "ङ्ढ", "\xb1": "+", "\xb4": "झ", "\xb6": "ठ्ठ",
	"\xb7": "ङ्ग", "·": "ङ्ग",
	"\xbf": "रू", "\xc5": "हृ", "\xc6": "”", "\xcb": "ङ्ग", "\xcc": "न्न", "\xcd": "ङ्क",
	"\xce": "ङ्ख", "\xd2": "\xa8", "\xd6": "=", "\xd7": "\xd7", "\xd8": "्य", "\xd9": ";",
	"\xda": "’", "\xdb": "!", "\xdc": "%", "\xdd": "ट्ठ", "\xdf": "द्म", "\xe5": "द्व",
	"\xe6": "“", "\xe7": "ॐ", "\xf7": "/",
}

# Differences from Preeti for related fonts
_FONT_DIFFS = {
	"kantipur": {
		"F": "ा", "X": "हृ", "†": "!", "‹": "ङ्ग", "Œ": "त्त्", "“": "ँ",
		"™": "र", "›": "ऽ", "œ": "त्र्", "\xa5": "र्‍", "\xa8": "ङ्ग",
		"\xac": "…", "\xad": "(", "\xae": "र", "\xb5": "र", "\xba": "फ्", "\xc2": "र",
		"\xc8": "ष", "\xce": "फ्", "\xcf": "फ्", "\xd4": "क्ष", "\xf8": "य्",
	},
	"sagarmatha": {
		"‚": ")", "ƒ": "द्र", "„": HALANT, "†": ";", "‡": "े",
		"ˆ": "ृ", "Š": "र्", "‹": "ै", "Œ": "त्त्", "‘": "‘",
		"’": "’", "“": "ँ", "”": "”", "œ": "त्र्", "\xa4": "!",
		"\xa5": "र्‍", "\xac": "ु", "\xad": "(", "\xae": "र", "\xb0": "ङ्क", "\xb5": "झ",
		"\xb7": "ङ्ग", "\xb8": "ड्ड", "\xc5": "फ", "\xc7": "फ्", "\xc8": "ष", "\xc9": "स",
		"\xd2": "ू", "\xd4": "क्ष", "\xd9": "ह", "\xde": "ह्", "\xe8": "द्भ", "\xf8": "य्",
	},
	"himali": {
		"X": "हृ",
		"\xa4": "ँ", "\xa5": "र्‍", "\xad": "(", "\xae": "+", "\xb0": "ङ्क", "\xbb": "",
		"\xd1": "ङ", "\xd2": "ू", "\xd4": "क्ष", "\xd9": "ह", "\xda": "ु", "\xe9": "ङ्ग",
		"\xed": "ष", "\xf8": "य्", "\xfa": "ू",
	},
	"pcs": {
		"F": "ा", "C": "र्‍",
		"<": "्र", "?": "रू", "\xa4": "ँ", "\xa5": "ऋ", "\xa9": "?", "\xaa": "ञ", "\xae": "+",
		"\xb0": "ङ्क", "\xb7": "ट्ठ", "\xbf": "रु", "\xd2": "ू", "\xd4": "क्ष", "\xd9": "ह",
		"\xe9": "ङ्ग", "\xed": "ष", "\xf1": "ङ", "\xf8": "य्", "\xfa": "ू",
	},
}

_PREETI_FAMILY_MAPS = {"preeti": PREETI_MAP}
for _name, _diff in _FONT_DIFFS.items():
	_m = dict(PREETI_MAP)
	_m.update(_diff)
	_PREETI_FAMILY_MAPS[_name] = _m

_MOD_BASES = {"उ": "ऊ", "भ": "झ", "प": "फ"}
_MOD_SKIPPABLE = SIGNS | {HALANT, "र", "य"}

_COMPOSE = [
	("ेा", "ाे"), ("ैा", "ाै"),  # े+ा / ै+ा typed in either order
	("अाे", "ओ"), ("अाै", "औ"), ("अा", "आ"), ("एे", "ऐ"),
	("ाे", "ो"), ("ाै", "ौ"),
]
_DEDUP = re.compile("([ँंेैुूाी])\\1+")


def _applyModifier(s):
	out = list(s)
	i = 0
	while i < len(out):
		if out[i] != _MOD:
			i += 1
			continue
		del out[i]
		# look back for the base this 'm' modifies
		j = i - 1
		while j >= 0 and out[j] in SIGNS:
			j -= 1
		# त्र / त्त / व्र + m  ->  क्र / क्त
		if j >= 2 and out[j - 1] == HALANT and out[j - 2] in ("त", "व") and out[j] in ("र", "त"):
			out[j - 2] = "क"
			continue
		k = j
		steps = 0
		while k >= 0 and out[k] not in _MOD_BASES and out[k] in _MOD_SKIPPABLE and steps < 3:
			k -= 1
			steps += 1
		if k >= 0 and out[k] in _MOD_BASES:
			out[k] = _MOD_BASES[out[k]]
		# otherwise the stray 'm' is dropped
	return "".join(out)


def _placeISign(s):
	"""Move ि typed before a consonant cluster to after it."""
	out = []
	i = 0
	n = len(s)
	while i < n:
		ch = s[i]
		if ch == _I:
			j = i + 1
			# a reph marker may sit between (rare); keep it attached after
			if j < n and s[j] in CONSONANTS:
				end = _clusterEnd(s, j)
				out.append(s[j:end])
				out.append(I_SIGN)
				i = end
				continue
			out.append(I_SIGN)
			i += 1
			continue
		out.append(ch)
		i += 1
	return "".join(out)


def _placeReph(s):
	"""Move reph marker typed after a syllable to र् before that syllable's cluster."""
	while _REPH in s:
		r = s.index(_REPH)
		j = r - 1
		while j >= 0 and s[j] in SIGNS:
			j -= 1
		if j >= 0 and (s[j] in CONSONANTS or s[j] == NUKTA):
			start = _clusterStart(s, j)
			s = s[:start] + "र" + HALANT + s[start:r] + s[r + 1:]
		else:
			s = s[:r] + "र" + HALANT + s[r + 1:]
	return s


def _fixSignOrder(s):
	# matra typed before a following half-letter: move it after the cluster
	s = re.sub("([ाी-ौँ-ः]+)(्(?:.्)*[^्])", r"\2\1", s)
	# anusvara/chandrabindu typed before a matra
	s = re.sub("([ँं])([ा-ौः]+)", r"\2\1", s)
	return s


BULLETS = set("•●○■▪◦✓★→←–—…*+-#~※♦►")
_DIGIT_MAP = str.maketrans("0123456789", "०१२३४५६७८९")


_C1 = {}
for _c in range(0x80, 0xA0):
	try:
		_C1[_c] = bytes([_c]).decode("cp1252")
	except UnicodeDecodeError:
		pass


# "¿" is रू in Preeti (x¿ हरू, b'¿kof]u दुरूपयोग) but some fonts of the family draw the
# u-sign there (lgs¿~h निकुञ्ज): the reading that gives a dictionary word wins.
_BF_CHOICES = ("रू", "ु", "रु")
_bfTables = {}


def _bfTable(font, sub):
	t = _bfTables.get((font, sub))
	if t is None:
		t = dict(_PREETI_FAMILY_MAPS.get(font, PREETI_MAP))
		t["\xbf"] = sub
		_bfTables[(font, sub)] = t
	return t


def _isWord(w):
	try:
		from . import neLexicon
	except ImportError:
		try:
			import neLexicon
		except ImportError:
			return False
	try:
		return neLexicon.isWord(w)
	except Exception:
		return False


def preetiFamilyToUnicode(text, font="preeti", _table=None):
	table = _table or _PREETI_FAMILY_MAPS.get(font, PREETI_MAP)
	if _table is None and "\xbf" in text and font in ("preeti", "kantipur", "himali", "sagarmatha", "fontasy"):
		parts = re.split(r"(\s+)", text)
		if len(parts) > 1:
			return "".join(preetiFamilyToUnicode(p, font) if p and not p.isspace() else p for p in parts)
		first = None
		for sub in _BF_CHOICES:
			out = preetiFamilyToUnicode(text, font, _bfTable(font, sub))
			if first is None:
				first = out
			if _isWord(out.strip(".,;:!?()[]{}\"'“”‘’।–—-")):
				return out
		return first
	# fonts without an encoding give raw codes 0x80-0x9F; the layouts are defined on Windows-1252
	text = text.translate(_C1)
	parts = re.split(r"(\s+)", text)
	result = []
	for word in parts:
		if not word or word.isspace():
			result.append(word)
			continue
		# Standalone bullet / symbol / emoji: preserve without conversion
		if word in BULLETS or (len(word) == 1 and word in "•●○■▪◦✓★→←–—…*+-#~※♦►") or any(ord(c) > 255 and not (0x0900 <= ord(c) <= 0x097F) for c in word):
			result.append(word)
			continue
		if font == "preeti":
			# Smart quote detection: C<word>D used as “<word>” in Preeti
			if word.startswith("C") and word.endswith("D") and len(word) >= 3:
				if not word.startswith(("Clif", "C0f", "Crt", "Crf", "C4b", "Cuj")):
					word = "“" + word[1:-1] + "”"
			# Preeti 'M' is the visarga (निःशुल्क lgMz'Ns, पुनः k'gM); alone it is a colon
			if word == "M":
				result.append(":")
				continue
		# Standalone digits (e.g. page numbers, list numbers, percentages, decimals):
		# in Preeti family layouts, unshifted digit keys give consonants/conjuncts (1=ज्ञ, 2=द्द);
		# standalone digit strings in documents are never words, always numbers.
		m_num = re.match(r"^([+\$€₹.,;:!?\(\)\[\]\{\}\-\–—/\\%]*)([0-9]+(?:[.,/:\-][0-9]+)*)([%.,;:!?\(\)\[\]\{\}\-\–—/\\%]*)$", word)
		if m_num and m_num.group(2) != "5":
			# (a lone "5" is the very common verb छ, not a number)
			lead, mid, trail = m_num.group(1), m_num.group(2), m_num.group(3)
			result.append(lead + (mid.translate(_DIGIT_MAP) if font == "himali" else mid) + trail)
			continue
		# In Preeti typing / OCR, 9 and 0 at word boundaries enclosing letters/words
		# represent unshifted bracket keys ( ) rather than consonants ढ and ण्.
		# E.g. 9s0 -> (s) -> (क), 9v0 -> (v) -> (ख), 9lzIff0 -> (lzIff) -> (शिक्षा)
		m90 = re.match(r"^9([^0-9\s]+)0$", word)
		if m90:
			word = "(" + m90.group(1) + ")"

		# Preserve parentheses around words, clauses, and numbers:
		# In Preeti layout, '(' is Shift+9 (mapped to digit ९) and ')' is Shift+0 (mapped to digit ०).
		# When '(' or ')' wrap a word, clause, or single letters/numbers (e.g. (s) -> (क), (lzIff) -> (शिक्षा), (!)->(१)),
		# they are parentheses, not digits. They are digits only in pure multi-digit Preeti numbers (e.g. @)@( = २०२९, @) = २०).
		# NOTE: '[' ']' '{' '}' are Preeti letters/matras (e.g. ] is e-kar / o-kar, } is ai-kar, [ is ri-kar, { is reph);
		# they MUST NOT be stripped as punctuation!
		lead_b = ""
		trail_b = ""
		if len(word) >= 2 and word[0] == "(" and word[-1] == ")":
			lead_b = "("
			trail_b = ")"
			word = word[1:-1]
		else:
			if word.startswith("(") and (len(word) == 1 or word[1] not in "!@#$%^&*()"):
				lead_b = "("
				word = word[1:]
			if word.endswith(")") and (len(word) == 1 or word[-2] not in "!@#$%^&*()"):
				trail_b = ")"
				word = word[:-1]

		if not word:
			result.append(lead_b + trail_b)
			continue

		# If word already has Devanagari characters: preserve boundary punctuation
		if any("\u0900" <= c <= "\u097f" for c in word):
			lead = len(word) - len(word.lstrip(".,;:!?()[]{}\"'“”‘’•–—…"))
			trail = len(word) - len(word.rstrip(".,;:!?()[]{}\"'“”‘’•–—…"))
			lp = word[:lead]
			rp = word[len(word) - trail:] if trail else ""
			core = word[lead:len(word) - trail] if trail else word[lead:]
			if not any(c.isascii() and c.isalpha() for c in core):
				result.append(lead_b + word + trail_b)
				continue
			if lp or rp:
				result.append(lead_b + lp + preetiFamilyToUnicode(core, font, _table) + rp + trail_b)
				continue
			# mixed letters with nothing to strip: convert it as one word below
		s = "".join(table.get(ch, ch) for ch in word)
		s = s.replace(HALANT + "ा", "")  # half letter + ा = full letter
		s = _applyModifier(s)
		s = s.replace("इ" + _REPH, "ई")
		s = _placeISign(s)
		s = _placeReph(s)
		s = _fixSignOrder(s)
		for a, b in _COMPOSE:
			s = s.replace(a, b)
		s = _DEDUP.sub(r"\1", s)
		s = s.replace("टृ", "ट्ट")
		if s.startswith("ः"):
			s = ":" + s[1:]
		if s == "महव":
			s = "महत्त्व"
		elif s == "महवको":
			s = "महत्त्वको"
		elif s == "महवराख्ने":
			s = "महत्त्व राख्ने"
		elif s == "महवपूर्ण":
			s = "महत्त्वपूर्ण"
		if font == "preeti" and s.startswith("ऋ") and s.endswith("म्") and len(s) >= 4:
			if not s.startswith(("ऋषि", "ऋण", "ऋतु", "ऋचा", "ऋद्धि", "ऋग्वेद")):
				s = "“" + s[1:-1] + "”"
		result.append(lead_b + s + trail_b)
	return unicodedata.normalize("NFC", "".join(result))


# ---------------------------------------------------------------------------
# Kruti Dev (Hindi)
# ---------------------------------------------------------------------------

_KRUTI_MAIN = [
	("\xf1", "॰"), ("Q+Z", "QZ+"), ("sas", "sa"), ("aa", "a"), (")Z", "र्द्ध"), ("ZZ", "Z"),
	("‘", '"'), ("’", '"'), ("“", "'"), ("”", "'"),
	("\xe5", "०"), ("ƒ", "१"), ("„", "२"), ("…", "३"), ("†", "४"),
	("‡", "५"), ("ˆ", "६"), ("‰", "७"), ("Š", "८"), ("‹", "९"),
	("\xb6+", "फ़्"), ("d+", "क़"), ("[+k", "ख़"), ("[+", "ख़्"), ("x+", "ग़"), ("T+", "ज़्"),
	("t+", "ज़"), ("M+", "ड़"), ("<+", "ढ़"), ("Q+", "फ़"), (";+", "य़"), ("j+", "ऱ"), ("u+", "ऩ"),
	("\xd9k", "त्त"), ("\xd9", "त्त्"), ("\xe4", "क्त"), ("–", "दृ"), ("—", "कृ"),
	("\xe9", "न्न"), ("™", "न्न्"), ("=kk", "=k"), ("f=k", "f="),
	("\xe0", "ह्न"), ("\xe1", "ह्य"), ("\xe2", "हृ"), ("\xe3", "ह्म"), ("\xbaz", "ह्र"), ("\xba", "ह्"),
	("\xed", "द्द"), ("{k", "क्ष"), ("{", "क्ष्"), ("=", "त्र"), ("\xab", "त्र्"),
	("N\xee", "छ्य"), ("V\xee", "ट्य"), ("B\xee", "ठ्य"), ("M\xee", "ड्य"), ("<\xee", "ढ्य"),
	("|", "द्य"), ("K", "ज्ञ"), ("}", "द्व"), ("J", "श्र"), ("V\xaa", "ट्र"), ("M\xaa", "ड्र"),
	("<\xaa\xaa", "ढ्र"), ("N\xaa", "छ्र"), ("\xd8", "क्र"), ("\xdd", "फ्र"), ("nzZ", "र्द्र"),
	("\xe6", "द्र"), ("\xe7", "प्र"), ("\xc1", "प्र"), ("xz", "ग्र"), ("#", "रु"), (":", "रू"),
	("v‚", "ऑ"), ("vks", "ओ"), ("vkS", "औ"), ("vk", "आ"), ("v", "अ"), ("b\xb1", "ईं"),
	("\xc3", "ई"), ("bZ", "ई"), ("b", "इ"), ("m", "उ"), ("\xc5", "ऊ"), (",s", "ऐ"), (",", "ए"),
	("_", "ऋ"), ("\xf4", "क्क"), ("d", "क"), ("Dk", "क"), ("D", "क्"), ("[k", "ख"), ("[", "ख्"),
	("x", "ग"), ("Xk", "ग"), ("X", "ग्"), ("\xc4", "घ"), ("?k", "घ"), ("?", "घ्"), ("\xb3", "ङ"),
	("pkS", "चै"), ("p", "च"), ("Pk", "च"), ("P", "च्"), ("N", "छ"), ("t", "ज"), ("Tk", "ज"),
	("T", "ज्"), (">", "झ"), ("\xf7", "झ्"), ("\xa5", "ञ"), ("\xea", "ट्ट"), ("\xeb", "ट्ठ"),
	("V", "ट"), ("B", "ठ"), ("\xec", "ड्ड"), ("\xef", "ड्ढ"), ("M+", "ड़"), ("<+", "ढ़"),
	("M", "ड"), ("<", "ढ"), (".k", "ण"), (".", "ण्"), ("r", "त"), ("Rk", "त"), ("R", "त्"),
	("Fk", "थ"), ("F", "थ्"), (")", "द्ध"), ("n", "द"), ("/k", "ध"), ("/", "ध्"), ("\xcb", "ध्"),
	("\xe8", "ध"), ("u", "न"), ("Uk", "न"), ("U", "न्"), ("i", "प"), ("Ik", "प"), ("I", "प्"),
	("Q", "फ"), ("\xb6", "फ्"), ("c", "ब"), ("Ck", "ब"), ("C", "ब्"), ("Hk", "भ"), ("H", "भ्"),
	("e", "म"), ("Ek", "म"), ("E", "म्"), (";", "य"), ("\xb8", "य्"), ("j", "र"), ("y", "ल"),
	("Yk", "ल"), ("Y", "ल्"), ("G", "ळ"), ("o", "व"), ("Ok", "व"), ("O", "व्"), ("'k", "श"),
	("'", "श्"), ('"k', "ष"), ('"', "ष्"), ("l", "स"), ("Lk", "स"), ("L", "स्"), ("g", "ह"),
	("\xc8", "ीं"), ("saz", "्रें"), ("z", "्र"), ("\xcc", "द्द"), ("\xcd", "ट्ट"), ("\xce", "ट्ठ"),
	("\xcf", "ड्ड"), ("\xd1", "कृ"), ("\xd2", "भ"), ("\xd3", "्य"), ("\xd4", "ड्ढ"), ("\xd6", "झ्"),
	("\xd8", "क्र"), ("\xd9", "त्त्"), ("\xdck", "श"), ("\xdc", "श्"), ("‚", "ॉ"),
	("kas", "ों"), ("ks", "ो"), ("kS", "ौ"), ("\xa1k", "ाँ"), ("ak", "kं"), ("k", "ा"),
	("ah", "ीं"), ("h", "ी"), ("aq", "ुं"), ("q", "ु"), ("aw", "ूं"), ("\xa1w", "ूँ"), ("w", "ू"),
	("`", "ृ"), ("̀", "ृ"), ("as", "ें"), ("\xb1s", "s\xb1"), ("s", "े"), ("aS", "ैं"),
	("S", "ै"), ("a\xaa", "्रं"), ("\xaa", "्र"), ("fa", "ंf"), ("a", "ं"), ("\xa1", "ँ"),
	("%", ":"), ("W", "ॅ"), ("•", "ऽ"), ("\xb7", "ऽ"), ("∙", "ऽ"), ("~j", "्र"),
	("~", HALANT), ("\\", "?"), ("+", NUKTA), ("^", "‘"), ("*", "’"), ("\xde", "“"),
	("\xdf", "”"), ("(", ";"), ("\xbc", "("), ("\xbd", ")"), ("\xc0", "}"), ("\xbe", "="),
	("A", "।"), ("-", "."), ("&", "-"), ("μ", "-"), ("Œ", "॰"), ("]", ","),
	("@", "/"), ("\xae", "ैं"),
]
_KRUTI_VOWELS = set("अआइईउऊएऐओऔािीुूृेैोौंःँॅ")
_KRUTI_UNATTACHED = list("ािीुूृेैोौंःँॅ")


def _krutiIBefore(text, marker, suffix):
	"""Kruti types ि (marker) before the consonant: marker + X -> X + suffix."""
	out = []
	i = 0
	n = len(text)
	while i < n:
		if text.startswith(marker, i):
			j = i + len(marker)
			if j < n:
				end = _clusterEnd(text, j) if text[j] in CONSONANTS else j + 1
				out.append(text[j:end] + suffix)
				i = end
			else:
				out.append(suffix)
				i = j
			continue
		out.append(text[i])
		i += 1
	return "".join(out)


def krutiDevToUnicode(text):
	text = text.replace(" \xaa", "\xaa").replace(" ~j", "~j").replace(" z", "z")
	for a, b in _KRUTI_MAIN:
		text = text.replace(a, b)
	text = text.replace("\xb1", "Zं").replace("\xc6", "र्f")
	text = _krutiIBefore(text, "f", I_SIGN)
	text = text.replace("\xc7", "fa").replace("\xaf", "fa").replace("\xc9", "र्fa")
	text = _krutiIBefore(text, "fa", I_SIGN + "ं")
	text = text.replace("\xca", "ीZ")
	# ि् + X -> ्X + ि   (repeat for longer clusters)
	prev = None
	while prev != text:
		prev = text
		text = re.sub("ि्(.)", "्\\1ि", text)
	text = text.replace(HALANT + "Z", "Z")
	# reph: Z after a syllable -> र् before its cluster
	while "Z" in text:
		r = text.index("Z")
		j = r - 1
		while j >= 0 and text[j] in _KRUTI_VOWELS:
			j -= 1
		if j >= 0 and text[j] in CONSONANTS | {NUKTA}:
			start = _clusterStart(text, j)
		else:
			start = j + 1 if j >= 0 else 0
		text = text[:start] + "र्" + text[start:r] + text[r + 1:]
	for m in _KRUTI_UNATTACHED:
		text = text.replace(" " + m, m).replace("," + m, m + ",")
	text = text.replace("््र", "्र").replace("्र्", "र्").replace("््", "्")
	return unicodedata.normalize("NFC", text)


# ---------------------------------------------------------------------------
# Font name detection
# ---------------------------------------------------------------------------

_FONT_NAME_PATTERNS = [
	(re.compile(r"preeti", re.I), "preeti"),
	(re.compile(r"kantipur", re.I), "kantipur"),
	(re.compile(r"sagarmatha", re.I), "sagarmatha"),
	(re.compile(r"himal", re.I), "himali"),
	(re.compile(r"pcs\s*nepali", re.I), "pcs"),
	(re.compile(r"\bsun\b|sumod|acharya|kanchan|everest|annapurna|jagadamba|rupa|shangrila", re.I), "preeti"),
	(re.compile(r"kruti\s*dev|krutidev|k010|kruti", re.I), "krutidev"),
]

ENCODINGS = ("preeti", "kantipur", "sagarmatha", "himali", "pcs", "krutidev")
NEPALI_ENCODINGS = ("preeti", "kantipur", "sagarmatha", "himali", "pcs")


def encodingForFontName(fontName):
	"""Return the legacy encoding id for a font name, or None if it is not a known legacy Devanagari font."""
	if not fontName:
		return None
	# PDFs often report subset names like 'ABCDEF+Preeti'
	for pat, enc in _FONT_NAME_PATTERNS:
		if pat.search(fontName):
			return enc
	return None


_DATE_DANDA = re.compile("(?<=[०-९])।(?=[०-९])")
_LONE_CANDRA = re.compile("(?<![\u0900-\u097f])ॅ")
# a visarga after a virama, or before a dash, or before "(" is the colon typed with the same key
_COLON = re.compile("(?<=्)ः|ः(?=\\s*[–—\\-(])|^ः$")


def convert(text, encoding="preeti"):
	if encoding == "krutidev":
		return krutiDevToUnicode(text)
	# (a "." between digits draws a danda in Preeti and is kept as the danda the page shows)
	out = preetiFamilyToUnicode(text, encoding)
	if "ॅ" in out:
		# "‘" draws ॅ in Preeti but a quote in many Preeti-layout fonts (Nagarik ...): a sign
		# with no letter before it is the quote
		out = _LONE_CANDRA.sub("‘", out)
	if "ः" in out:
		out = _COLON.sub(":", out)
	return out


def languageForEncoding(encoding):
	return "hi" if encoding == "krutidev" else "ne"
