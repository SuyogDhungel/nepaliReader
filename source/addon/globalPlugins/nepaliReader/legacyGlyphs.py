# -*- coding: utf-8 -*-
"""Identify legacy font resources by outlines, not by their reported name.

The reference contains outline fingerprints and canonical legacy keys, never
font binaries. A match recovers keys even after PDF subsetting renumbers codes.
Unknown outlines remain unknown; script/headline detection is not a font map.
"""
import json
import os

try:
	from . import legacyFonts
except ImportError:
	import legacyFonts

_references = None


def _load():
	global _references
	if _references is None:
		try:
			with open(os.path.join(os.path.dirname(__file__), "legacyGlyphRefs.json"), encoding="utf-8") as f:
				_references = json.load(f)["fonts"]
		except (OSError, ValueError, KeyError):
			_references = []
	return _references


def identify(font, sf, gidForCode):
	"""Return (encoding, code->key) only for an independently supported match.

	Use at least four distinct used outlines and two letter keys. A full font
	can also identify a symbol-only run using twelve unused cmap outlines.
	Require every used nonblank outline to be covered; partial matches must
	not turn the unknown remainder into guessed Preeti keys.
	"""
	used = {}
	for code in font.used:
		g = gidForCode(code)
		h = sf.glyphHash(g) if g else None
		if h:
			used[code] = h
	if not used:
		return None
	candidates = []
	for ref in _load():
		keys = ref.get("keys", {})
		matched = {code: keys[h] for code, h in used.items() if h in keys}
		if len(matched) != len(used):
			continue
		unique = set(used.values())
		letters = {k for k in matched.values() if k.isascii() and k.isalpha()}
		supported = len(unique) >= 4 and len(letters) >= 2
		if not supported:
			try:
				hashes = {sf.glyphHash(g) for g in set(sf.cmap().values())}
				supported = len(hashes.intersection(keys)) >= 12
			except Exception:
				supported = False
		if supported:
			candidates.append((ref["encoding"], matched, ref.get("overrides", {})))
	if not candidates:
		return None
	first = candidates[0]
	def meanings(candidate):
		enc, mapping, overrides = candidate
		table = dict(legacyFonts.keyTable(enc))
		table.update(overrides)
		return {code: table.get(key, key) for code, key in mapping.items()}
	if any(meanings(c) != meanings(first) for c in candidates[1:]):
		return None
	return first
