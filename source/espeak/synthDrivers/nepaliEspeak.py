# -*- coding: utf-8 -*-
# Nepali eSpeak for NVDA: NVDA's own eSpeak NG, speaking Nepali in its Nepali voice and English in
# its English voice, wherever the text is - a web page with no lang="ne", an app, a menu.
# Copyright (C) 2026 Suyog Dhungel, Roshan Gautam. Licensed under the GNU GPL v2 or later.
#
# The synthesizer never changes what it is given to say. Text that can be wrong (Preeti, damaged
# Unicode in PDFs) is put right before it gets here, by the Nepali Reader built into this add-on
# (globalPlugins/nepaliEspeakReader), which can see the document.

import re

from synthDrivers.espeak import SynthDriver as _EspeakDriver
from speech.commands import LangChangeCommand

# languages written in Devanagari: a page or a document that says its text is one of them is
# read in that language; any other Devanagari text is Nepali
_DEVA_LANGS = frozenset(("ne", "hi", "mr", "sa", "mai", "bho", "new", "kok", "doi", "brx", "sd", "awa", "mag"))
# a run of Devanagari (letters, signs, digits, dandas), of Latin letters, or of other letters;
# what is between them (spaces, ASCII digits, punctuation) goes with the run beside it
_RUNS = re.compile(
	"([ऀ-ॿ꣠-ꣿ᳐-᳿]+)"
	"|([A-Za-zÀ-ɏḀ-ỿ]+)"
	"|([^\\W\\d_]+)"
)


def _base(lang):
	return (lang or "").lower().replace("_", "-").split("-")[0]


def runs(text):
	"""[(kind, piece)] for a text: kind is "deva", "latin", "other", or None when the text has no
	letters at all (a number, a sign: it keeps the language it is in)."""
	parts = []
	pos = 0
	for m in _RUNS.finditer(text):
		if m.start() > pos:
			parts.append([None, text[pos:m.start()]])
		kind = "deva" if m.group(1) else "latin" if m.group(2) else "other"
		parts.append([kind, m.group(0)])
		pos = m.end()
	if pos < len(text):
		parts.append([None, text[pos:]])
	kinds = [k for k, _p in parts if k]
	if not kinds:
		return [(None, text)]
	# what has no letters goes with the run before it (at the start: the run after it)
	prev = None
	for part in parts:
		if part[0] is None:
			part[0] = prev
		else:
			prev = part[0]
	first = kinds[0]
	for part in parts:
		if part[0] is None:
			part[0] = first
	out = []
	for kind, piece in parts:
		if out and out[-1][0] == kind:
			out[-1] = (kind, out[-1][1] + piece)
		else:
			out.append((kind, piece))
	return out


def languageFor(kind, declared, voiceLang):
	"""The language to speak a run in (None: the voice's own). `declared`: what NVDA said the text
	is (a page's lang attribute), `voiceLang`: the language of the chosen voice."""
	d = _base(declared)
	v = _base(voiceLang)
	if kind == "deva":
		if d in _DEVA_LANGS:
			return declared
		return None if v == "ne" else "ne"
	if kind == "latin":
		if declared and d not in _DEVA_LANGS:
			return declared
		return "en" if v in _DEVA_LANGS else None
	return declared


def switchLanguages(speechSequence, voiceLang):
	"""The speech sequence with a language change wherever the script changes. NVDA's own language
	changes are kept as what the text is declared to be."""
	out = []
	declared = None
	cur = None  # the language being spoken (None: the voice's own)
	for item in speechSequence:
		if isinstance(item, LangChangeCommand):
			declared = item.lang
			continue
		if not isinstance(item, str) or not item:
			out.append(item)
			continue
		for kind, piece in runs(item):
			if kind is not None:
				lang = languageFor(kind, declared, voiceLang)
				if lang != cur:
					out.append(LangChangeCommand(lang))
					cur = lang
			out.append(piece)
	return out


class SynthDriver(_EspeakDriver):
	name = "nepaliEspeak"
	description = "Nepali eSpeak"

	def speak(self, speechSequence):
		try:
			seq = switchLanguages(speechSequence, getattr(self, "_language", None))
		except Exception:
			seq = speechSequence
		super().speak(seq)
