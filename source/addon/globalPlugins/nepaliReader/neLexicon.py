# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - offline Nepali word check.
# Data: the Nepali Hunspell dictionary (LibreOffice / Madan Puraskar Pustakalaya, LGPL 2.1):
# about 36,000 stems plus the dictionary's suffix rules, which together cover about
# 2.5 million word forms. Checked like a spell checker, so nothing is expanded in memory.
# No NVDA dependencies.

import json
import os
import re
import zlib

_STEMS = {}
_SFX = {}      # added ending -> [(flag, strip, compiled condition)]
_PFX = {}
_SFX_LENGTHS = []
_EXTRA = frozenset()  # Hindi words (wordfreq) so Hindi text is recognised too
_NAMES = frozenset()  # Nepal place names and newer common words, also with the usual endings
_NAME_ENDINGS = ("हरूको", "हरूमा", "हरूले", "हरू", "देखि", "सम्म", "बाट", "लाई", "भित्र", "को", "का", "की", "मा", "ले", "मै", "कै")
_COMMON_NEPALI = frozenset({
	"भनसुन", "चाकडी", "नियुक्ति", "उपेन्द्र", "उपेन्द्रबहादुर", "मेरिटोक्रेसी",
})
_loaded = False


def load(path=None):
	global _STEMS, _SFX, _PFX, _SFX_LENGTHS, _loaded
	if path is None:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nepaliWords.dat")
	with open(path, "rb") as f:
		data = json.loads(zlib.decompress(f.read()).decode("utf-8"))
	stems = {}
	for w, flags in data["stems"].items():
		stems[w] = frozenset(x for x in flags.split(",") if x)
	sfx = {}
	for flag, entries in data["rules"]["SFX"].items():
		for strip, add, cond in entries:
			sfx.setdefault(add, []).append((flag, strip, re.compile("(?:" + (cond if cond != "." else ".") + ")$")))
	pfx = {}
	for flag, entries in data["rules"]["PFX"].items():
		for strip, add, cond in entries:
			pfx.setdefault(add, []).append((flag, strip, re.compile("^(?:" + (cond if cond != "." else ".") + ")")))
	_STEMS, _SFX, _PFX = stems, sfx, pfx
	_SFX_LENGTHS = sorted({len(a) for a in sfx}, reverse=True)
	global _EXTRA
	hindi = os.path.join(os.path.dirname(path), "hindiWords.dat")
	if os.path.exists(hindi):
		with open(hindi, "rb") as f:
			_EXTRA = frozenset(zlib.decompress(f.read()).decode("utf-8").split("\n"))
	global _NAMES
	names = os.path.join(os.path.dirname(path), "placeNames.dat")
	if os.path.exists(names):
		with open(names, "rb") as f:
			_NAMES = frozenset(zlib.decompress(f.read()).decode("utf-8").split("\n"))
	_loaded = True
	return len(stems) + len(_EXTRA) + len(_NAMES)


def isLoaded():
	return _loaded


def isWord(word):
	"""True if `word` is a Nepali word form known to the dictionary."""
	if not word:
		return False
	if word in _STEMS or word in _EXTRA or word in _NAMES or word in _COMMON_NEPALI:
		return True
	for e in _NAME_ENDINGS:
		if word.endswith(e) and (word[: -len(e)] in _NAMES or word[: -len(e)] in _COMMON_NEPALI):
			return True
	n = len(word)
	for L in _SFX_LENGTHS:
		if L > n - 1:
			continue
		add = word[n - L:] if L else ""
		entries = _SFX.get(add)
		if not entries:
			continue
		base = word[: n - L] if L else word
		for flag, strip, cond in entries:
			stem = base + strip
			flags = _STEMS.get(stem)
			if flags is not None and flag in flags and cond.search(stem):
				return True
	for add, entries in _PFX.items():
		if add and word.startswith(add):
			for flag, strip, cond in entries:
				stem = strip + word[len(add):]
				flags = _STEMS.get(stem)
				if flags is not None and flag in flags and cond.search(stem):
					return True
	return False
