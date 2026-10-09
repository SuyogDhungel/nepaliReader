# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - decides whether ASCII text is really a legacy
# Devanagari font (Preeti family / Kruti Dev) or ordinary English.
# No NVDA dependencies.

import re

try:
	from .detectorModel import MODEL
	from . import neLexicon
	from . import legacyFonts
except ImportError:  # unit tests
	from detectorModel import MODEL
	import neLexicon
	import legacyFonts

# Very common English words, plus words NVDA itself speaks (roles, states).
# These are never treated as legacy text unless the whole line is overwhelmingly legacy.
COMMON_ENGLISH = set("""
a about above after again against all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having
he her here hers herself him himself his how i if in into is it its itself just me more most my myself no
nor not now of off on once only or other our ours ourselves out over own same she should so some such than
that the their theirs them themselves then there these they this those through to too under until up very
was we were what when where which while who whom why will with would you your yours yourself yourselves
yes ok okay cancel close open save file edit view help tools window home back next previous new delete
insert format page pages level heading headings link visited button check box checked not unchecked radio menu item
bar tab list table row column cell graphic image document dialog edit text clipboard selected unselected
blank out of focus expanded collapsed pressed unavailable read only required invalid entry has popup
description descriptions gvt gov govt landmark landmarks
search address settings options start end top bottom left right up down enter escape space shift control
alt windows desktop folder name date time size type modified one two three four five six seven eight nine
ten first last please thank thanks hello hi welcome sign log login logout account password email user
mail inbox sent draft reply forward send message chat call video share like comment follow more less
show hide play pause stop volume mute copy cut paste undo redo find replace print zoom full screen
""".split())

_A11Y_GLUED_AFTER = re.compile(
	r'([^\s])(Description:|graphic\b|image\b|landmark\b|heading\b|level\s*\d+\b|button\b|link\b|Page\s*\d+\b|table\b|row\s*\d+\b|column\s*\d+\b)',
	re.I
)
_A11Y_GLUED_BEFORE = re.compile(
	r'\b(Description:|graphic|image|landmark|heading|level\s*\d+|button|link|Page\s*\d+|table|row\s*\d+|column\s*\d+)([A-Za-z\u0900-\u097f])',
	re.I
)
_PAREN_NUM_AFTER = re.compile(r'([^\s\(\[\{])(\([0-9]+\)|\[[0-9]+\])')
_PAREN_NUM_BEFORE = re.compile(r'(\([0-9]+\)|\[[0-9]+\])([^\s\)\]\}])')
_BULLET_SYMS = '•‣⁃▪▫○●★☆✓✔►◄→←↑↓↔⇒⇐◆◇◈◉◎§¶※†‡©®™°±×÷≠≤≥∞≈‰➢➤✦✧❖▲▼◀▶'
# these are also letters of the Preeti keyboard (÷ is "/", § is ट्ट, ‰ is झ्, • is ड्ड ...): inside a
# word they belong to the word, so they never split it and never mark it as "not Preeti"
_PREETI_KEY_SYMS = '•§¶†‡©®™°±×÷‰'
_PURE_BULLETS = ''.join(c for c in _BULLET_SYMS if c not in _PREETI_KEY_SYMS)
_BULLET_GLUED_BEFORE = re.compile(r'([' + _PURE_BULLETS + r'])([^\s' + _PURE_BULLETS + r'])')
_BULLET_GLUED_AFTER = re.compile(r'([^\s' + _PURE_BULLETS + r'])([' + _PURE_BULLETS + r'])')
_DOT_BULLET_BEFORE = re.compile(r'(?<![A-Za-z0-9])(•)([^\s•])')
_DOT_BULLET_AFTER = re.compile(r'([^\s•A-Za-z0-9])(•)')


def cleanGluedTokens(s):
	if not s:
		return s
	s = _A11Y_GLUED_AFTER.sub(r'\1 \2', s)
	s = _A11Y_GLUED_BEFORE.sub(r'\1 \2', s)
	s = _PAREN_NUM_AFTER.sub(r'\1 \2', s)
	s = _PAREN_NUM_BEFORE.sub(r'\1 \2', s)
	s = _BULLET_GLUED_BEFORE.sub(r'\1 \2', s)
	s = _BULLET_GLUED_AFTER.sub(r'\1 \2', s)
	s = _DOT_BULLET_BEFORE.sub(r'\1 \2', s)
	s = _DOT_BULLET_AFTER.sub(r'\1 \2', s)
	return s


# Patterns typed in Preeti that essentially never occur inside English words
_PREETI_SIGNATURE = re.compile(r"[a-zA-Z;/:][\]\}][a-zA-Z;:/'\"]|[a-zA-Z][\]\}]$|f[\]\}]|[a-zA-Z]\{|[a-zA-Z]\\[a-zA-Z]|[a-zA-Z]\|[a-zA-Z]|^l[a-zA-Z:;]|[a-zA-Z]'[a-zA-Z/]{2}|[a-zA-Z]\"[a-zA-Z/]")
# Kruti Dev: ि typed as 'f' before a consonant, matras like 'k','h','s' after consonants
_KRUTI_SIGNATURE = re.compile(r"(?:^|[^a-zA-Z])f[a-zA-Z\[\"';]|[dxprtnuiceyjlogDXPRTNUICEYLOG]k[a-zA-Z]|ks$|kS$|Z$|[a-zA-Z]Z[a-zA-Z]|\xa1")

_URLISH = re.compile(r"^(?:https?://|www\.)|@[\w-]+\.|\.(?:com|org|net|np|in|gov|edu)\b|^[\w.-]+\.(?:exe|dll|pdf|docx?|txt|html?|py|js)$", re.I)
_STRIP = ".,!?()…"
# programming code / markup: never guessed as legacy text (font names still apply)
_CODE_SIGNALS = re.compile(r"==|!=|<=|>=|=>|&&|\|\||\+\+|\(\)|\)\s*\{|;\s*$|\s=\s|</\w|/>|\b(?:def|return|function|var|let|const|import|class|public|void|int|if|else|for|while|print|null|true|false|self|this)\b")


def _looksLikeCode(text):
	return len(set(m.group(0).strip() for m in _CODE_SIGNALS.finditer(text))) >= 2

# Full offline English dictionary (Webster's 2nd + modern words), loaded once in the background.
_ENGLISH_DICT = frozenset()


def loadDictionary(path=None):
	"""Load the compressed English word list. Safe to call from a background thread."""
	global _ENGLISH_DICT
	import os
	import zlib
	if path is None:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "englishWords.dat")
	with open(path, "rb") as f:
		_ENGLISH_DICT = frozenset(zlib.decompress(f.read()).decode("utf-8").split("\n"))
	return len(_ENGLISH_DICT)


_SUFFIXES = ("'s", "s'", "ies", "es", "s", "ed", "ing", "ly", "er", "est")


def isEnglishWord(word):
	global _ENGLISH_DICT
	if not _ENGLISH_DICT:
		try:
			loadDictionary()
		except Exception:
			pass
	w = word.lower()
	if w in COMMON_ENGLISH or w in _ENGLISH_DICT:
		return True
	if not _ENGLISH_DICT or not w.isascii():
		return False
	for suf in _SUFFIXES:
		if w.endswith(suf) and len(w) - len(suf) >= 3:
			stem = w[: -len(suf)]
			if stem in _ENGLISH_DICT or (suf == "ies" and stem + "y" in _ENGLISH_DICT) or (suf in ("ed", "ing", "er", "est") and stem + "e" in _ENGLISH_DICT):
				return True
	return False


WORD_THRESHOLD = 3.0       # word looks legacy
STRONG_WORD = 6.0          # single word on its own is accepted (needs 4+ letters or a signature)
ENGLISH_THRESHOLD = -1.0   # word looks English
MIXED_WORD = 14.0          # a legacy word inside an English line (mixed-font documents)


def _core(token):
	return token.strip(_STRIP)


def wordScore(token, encoding="preeti"):
	"""Positive = looks like the legacy encoding, negative = looks English."""
	w = _core(token)
	if not w or not any(c.isalpha() for c in w):
		return 0.0
	if _URLISH.search(token):
		return -20.0
	table = MODEL["kruti" if encoding == "krutidev" else "preeti"]
	s = "^" + w + "$"
	score = 0.0
	for i in range(len(s) - 1):
		score += table.get(s[i:i + 2], 0.0)
	sig = _KRUTI_SIGNATURE if encoding == "krutidev" else _PREETI_SIGNATURE
	hits = len(sig.findall(w))
	score += 4.0 * min(hits, 3)
	if w.lower() in COMMON_ENGLISH:
		score -= 12.0
	elif len(w) >= 3 and isEnglishWord(w):
		score -= 6.0
	return score


def _isScorable(token):
	return any(c.isascii() and c.isalpha() for c in _core(token))


def _strongAlone(token, sc, encoding):
	core = _core(token)
	sig = _KRUTI_SIGNATURE if encoding == "krutidev" else _PREETI_SIGNATURE
	if sig.search(core):
		return sc >= STRONG_WORD - 3
	if neLexicon.isLoaded():
		conv = legacyFonts.convert(core, encoding)
		if conv and neLexicon.isWord(conv.strip(_STRIP)) and not isEnglishWord(core.lower()):
			return True
	return sc >= STRONG_WORD and len(core) >= 4 and not core.isupper()


def isNonLegacySymbolOrEmoji(t):
	if not t:
		return False
	if any(ord(c) > 255 and not (0x0900 <= ord(c) <= 0x097F) and c not in legacyFonts.PREETI_MAP for c in t):
		return True
	if any(c in _PURE_BULLETS for c in t):
		return True
	if any(c in _PREETI_KEY_SYMS for c in t) and not any(c.isalnum() for c in t):
		return True  # a bare sign such as § or ÷ standing alone is a sign, not a word
	if t in _STANDALONE_BULLET:
		return True
	return False


def decide(text, encoding="preeti", context=False):
	"""Return a list of (token, isLegacy) covering `text` (whitespace tokens included, never legacy).

	* Lines that are clearly legacy (most scorable words legacy-like) are converted whole,
	  except tokens that look like URLs / e-mails / file names.
	* Lines that are mostly English are left alone, apart from individual words with very
	  strong legacy evidence (mixed documents).
	* A single word is converted only with strong evidence.
	* `context=True` means the surrounding document was recently confirmed legacy, so short
	  fragments (single words, characters) lean towards legacy unless they look English.
	"""
	text = cleanGluedTokens(text)
	if not context and _looksLikeCode(text):
		return [(t, False) for t in re.split(r"(\s+)", text)]
	tokens = re.split(r"(\s+)", text)
	scored = []
	legacy = english = 0
	hasDeva = any("\u0900" <= c <= "\u097f" for c in text)
	for t in tokens:
		if not t or t.isspace() or not _isScorable(t) or any("\u0900" <= c <= "\u097f" for c in t):
			scored.append((t, None))
			continue
		sc = wordScore(t, encoding)
		core = _core(t)
		if sc >= WORD_THRESHOLD and len(core) >= 3 and isEnglishWord(core):
			sig = _KRUTI_SIGNATURE if encoding == "krutidev" else _PREETI_SIGNATURE
			if not sig.search(core):
				sc = ENGLISH_THRESHOLD  # a real English word without legacy-only key patterns
		scored.append((t, sc))
		if sc >= WORD_THRESHOLD:
			legacy += 1
		elif sc <= ENGLISH_THRESHOLD:
			english += 1
	total = legacy + english
	if total == 0:
		hasScorable = any(sc is not None and sc > 0 for _, sc in scored)
		if context and hasScorable:
			# ambiguous fragment inside a legacy document: only convert if it has ASCII letters and is not a bullet/arrow/emoji/number
			return [(t, bool(t) and any(c.isascii() and c.isalpha() for c in t) and not isNonLegacySymbolOrEmoji(t) and not _NUM_TOKEN.match(t.strip(_STRIP)) and not _URLISH.search(t)) for t, _ in scored]
		return [(t, False) for t, _ in scored]
	if context and not hasDeva:
		wholeLine = legacy >= english and not any(
			sc is not None and sc <= -10 for _, sc in scored if len(scored) <= 3)
		if not wholeLine and english == 0:
			wholeLine = True
	elif not hasDeva:
		wholeLine = (legacy >= 2 and legacy >= 3 * english) or (
			legacy >= 1 and english == 0 and any(sc is not None and _strongAlone(t, sc, encoding) for t, sc in scored))
	else:
		wholeLine = False
	result = []
	for t, sc in scored:
		core = _core(t)
		if not t or t.isspace() or any("\u0900" <= c <= "\u097f" for c in t):
			result.append((t, False))
		elif isPreetiSymbolNumber(t) and (wholeLine or legacy > 0):
			result.append((t, True))
		elif isNonLegacySymbolOrEmoji(t) or isNonLegacySymbolOrEmoji(core):
			result.append((t, False))
		elif core == "5" and (wholeLine or (legacy > 0 and english == 0)) and encoding != "krutidev":
			# in a Preeti line a lone 5 is the very common verb छ (the key 5), not the number five
			result.append((t, True))
		elif _NUM_TOKEN.match(core) or _NUM_TOKEN.match(t):
			result.append((t, False))
		elif wholeLine:
			# keep words that clearly read as English/romanised ("roshan", "Office") inside a legacy line
			sig = _KRUTI_SIGNATURE if encoding == "krutidev" else _PREETI_SIGNATURE
			# short dictionary words are often Preeti too (eft भात, ag बन): inside a legacy line
			# only longer English words, or words that score clearly English, are kept
			englishLooking = (
				((sc is not None and sc <= ENGLISH_THRESHOLD * 4) or (isEnglishWord(core) and len(core) >= 5))
				and len(core) >= 3
				and not sig.search(core)
			)
			hasLetters = any(c.isascii() and c.isalpha() for c in t)
			result.append((t, not _URLISH.search(t) and not englishLooking and (hasLetters or not t.replace(".", "").isdigit())))
		else:
			isBulletPrefix = (bool(re.match(r"^9[a-zA-Z]+0$", t)) or bool(_PREETI_LIST_TOKEN.match(t)) or (len(core) == 1 and core.islower() and (t[-1:] in "_).-/" or t[:1] in "([") and legacy > 0))
			result.append((t, bool(
				isBulletPrefix
				or (legacy > 0 and isPreetiSymbolNumber(t))
				or (sc is not None and (
					(legacy > english and _strongAlone(t, sc, encoding))
					or (sc >= MIXED_WORD and len(_core(t)) >= 3 and not isEnglishWord(_core(t))
						and encoding != "krutidev" and _PREETI_SIGNATURE.search(_core(t))))))))
	return result


def looksLegacy(text, encoding="preeti", context=False):
	if any(flag for _, flag in decide(text, encoding, context)):
		return True
	core = text.strip()
	if core and neLexicon.isLoaded() and not isEnglishWord(core.lower()):
		conv = legacyFonts.convert(core, encoding)
		if conv and neLexicon.isWord(conv.strip(_STRIP)):
			return True
	return False


def convertMixed(text, converter, encoding="preeti", context=False):
	"""Convert only the parts of `text` the detector judges to be legacy-encoded."""
	out = []
	run = []
	for tok, isLegacy in decide(text, encoding, context):
		if isLegacy or (run and tok.isspace()):
			run.append(tok)
			continue
		if run:
			out.append(_flush(run, converter))
			run = []
		out.append(tok)
	if run:
		out.append(_flush(run, converter))
	return "".join(out)


def _flush(run, converter):
	# keep trailing whitespace outside the converted run
	trail = ""
	while run and run[-1].isspace():
		trail = run.pop() + trail
	return converter("".join(run)) + trail


# words and phrases NVDA itself speaks for controls; never converted when they are the whole utterance
NVDA_PHRASES = frozenset(p.strip() for p in """
button|edit|link|visited|visited link|heading|list|list item|table|row|column|cell|graphic|document|dialog|menu|
menu item|menu bar|tool bar|toolbar|tab|tab control|check box|checked|not checked|unchecked|radio button|selected|
not selected|unselected|expanded|collapsed|pressed|not pressed|unavailable|read only|required|invalid entry|
has popup|blank|out of list|clickable|editable|multi line|focused|busy indicator|status bar|title bar|scroll bar|
combo box|progress bar|slider|landmark|region|navigation|main|banner|form|search|article|frame|section|
paragraph|page|end of document|top|bottom|bold|italic|underline|not bold|not italic|clipboard|no selection
""".replace("\n", "").split("|") if p.strip())


_NUM_TOKEN = re.compile(r"^[\$€₹#№]?\d+(?:[.,/:\-]\d+)*[%°]?$")
# digits typed on Preeti's shifted number row: !(*) = १९८०, @)&* = २०७८ (a bracket pair around
# symbols, as in (!) or (@), is a clause marker and is left to the converter)
_PREETI_SYMNUM = re.compile(r"^[!@#$%^&*()\u00f7]{2,}[.,]?$")


def isPreetiSymbolNumber(t):
	core = (t or "").strip()
	if not _PREETI_SYMNUM.match(core):
		return False
	body = core.rstrip(".,")
	if body[0] == "(" and body[-1] == ")":
		return False
	return True


_PREETI_LIST_TOKEN = re.compile(r"^(?:[svu3ª][_\-]|[\(\[]?[svu3ª][\)\]./\-_]|9[svu3ª]0)$")
_STANDALONE_BULLET = frozenset("•●○■▪◦✓★→←–—…*+-#~※♦►")


def forceDecide(text, protectEnglish=True):
	"""Everything is legacy except URLs/e-mails, English numbers, standalone bullets/symbols,
	and (if protectEnglish) words NVDA itself speaks."""
	if not protectEnglish and text.strip().lower() in NVDA_PHRASES:
		return [(text, False)]
	out = []
	for t in re.split(r"(\s+)", text):
		if not t or t.isspace():
			out.append((t, False))
			continue
		core = _core(t)
		if _PREETI_LIST_TOKEN.match(t) or isPreetiSymbolNumber(t):
			out.append((t, True))
			continue
		if isNonLegacySymbolOrEmoji(t) or isNonLegacySymbolOrEmoji(core) or t in _STANDALONE_BULLET or core in _STANDALONE_BULLET:
			out.append((t, False))
			continue
		if _NUM_TOKEN.match(core) or _NUM_TOKEN.match(t):
			out.append((t, False))
			continue
		keep = _URLISH.search(t) or (protectEnglish and core.lower() in COMMON_ENGLISH and len(core) > 2)
		out.append((t, not keep))
	return out


def convertTokens(decisions, converter):
	out = []
	run = []
	for tok, isLegacy in decisions:
		if isLegacy or (run and tok.isspace()):
			run.append(tok)
			continue
		if run:
			out.append(_flush(run, converter))
			run = []
		out.append(tok)
	if run:
		out.append(_flush(run, converter))
	return "".join(out)
