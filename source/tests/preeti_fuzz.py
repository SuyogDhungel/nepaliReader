# Round-trip fuzz for the Preeti converter: Unicode Nepali words are typed as Preeti keystrokes by an
# independent encoder (written for this test only, from the Preeti keyboard: npttf2utf / preeti.js
# character maps and the glyphs of the Preeti font embedded in real PDFs), converted back with
# legacyFonts.convert and compared.  Typing variants that real typists use are chosen at random
# (seeded): reph before/after the vowel sign, क्र as s| or qm, फ as km, द्ध as 4 or b\w ...
#   python3 tests/preeti_fuzz.py [N words] [--show K]
import sys, random, re, unicodedata, collections, json, zlib, os
sys.path.insert(0, 'addon/globalPlugins/nepaliReader')
import legacyFonts as LF

N = lambda s: unicodedata.normalize('NFC', s)
H = '्'
# full consonants
FULL = {'क': 's', 'ख': 'v', 'ग': 'u', 'घ': '3', 'ङ': 'ª', 'च': 'r', 'छ': '5', 'ज': 'h', 'झ': ['´', 'em'],
	'ञ': '`', 'ट': '6', 'ठ': '7', 'ड': '8', 'ढ': '9', 'ण': '0f', 'त': 't', 'थ': 'y', 'द': 'b', 'ध': 'w',
	'न': 'g', 'प': 'k', 'फ': 'km', 'ब': 'a', 'भ': 'e', 'म': 'd', 'य': 'o', 'र': '/', 'ल': 'n', 'व': 'j',
	'श': 'z', 'ष': 'if', 'स': ';', 'ह': 'x'}
# half forms (consonant + virama) that have their own key
HALF = {'क': 'S', 'ख': 'V', 'ग': 'U', 'घ': '£', 'च': 'R', 'ज': 'H', 'झ': '‰', 'ञ': '~', 'ण': '0', 'त': 'T',
	'थ': 'Y', 'ध': 'W', 'न': 'G', 'प': 'K', 'फ': ['ˆ', 'Km'], 'ब': 'A', 'भ': 'E', 'म': 'D', 'ल': 'N', 'व': 'J',
	'श': 'Z', 'ष': 'i', 'स': ':', 'ह': 'X'}
# conjunct glyphs (full forms), longest first
CONJ = [('क्ष', 'If'), ('ज्ञ', '1'), ('त्त', ['Q', 'Tt']), ('द्द', ['2', 'b\\b']), ('द्ध', ['4', 'b\\w']),
	('द्य', ['B', 'b\\o']), ('द्व', ['å', 'b\\j']), ('द्म', ['ß', 'b\\d']), ('ट्ट', ['§', '6\\6']),
	('ठ्ठ', '¶'), ('ड्ड', ['•', '8\\8']), ('ङ्ग', ['Ë', 'ª\\u']), ('ङ्क', ['Í', 'ª\\s']), ('ङ्ख', 'Î'),
	('ङ्घ', '‹'), ('ट्ठ', 'Ý'), ('द्घ', '¢'), ('न्न', ['Gg', 'Ì'])]
# conjunct half forms
CONJ_HALF = [('क्ष', 'I'), ('ज्ञ', '¡')]
MATRA = {'ा': 'f', 'ी': 'L', 'ु': "'", 'ू': '"', 'ृ': '[', 'े': ']', 'ै': '}', 'ो': 'f]', 'ौ': 'f}'}
MOD = {'ं': '+', 'ँ': 'F', 'ः': 'M'}
VOWEL = {'अ': 'c', 'आ': 'cf', 'इ': 'O', 'ई': 'O{', 'उ': 'p', 'ऊ': 'pm', 'ऋ': 'C', 'ए': 'P', 'ऐ': 'P}',
	'ओ': 'cf]', 'औ': 'cf}'}
DIGIT = dict(zip('०१२३४५६७८९', ')!@#$%^&*('))
PUNCT = {'।': '.', ',': ',', '?': '<', '(': '-', ')': '_', '.': '='}
CONS = set(FULL)


class Skip(Exception):
	pass


def pick(rng, v):
	return rng.choice(v) if isinstance(v, list) else v


def encCluster(cons, rng):
	"""cons: list of consonants of one cluster (no reph, no र-phala). Returns keys."""
	out = []
	i = 0
	n = len(cons)
	while i < n:
		last = i == n - 1
		# conjunct glyphs
		done = False
		for u, k in CONJ:
			parts = u.split(H)
			L = len(parts)
			if cons[i:i + L] == parts and i + L == n:
				out.append(pick(rng, k))
				i += L
				done = True
				break
			if cons[i:i + L] == parts and i + L < n:
				for uh, kh in CONJ_HALF:
					if uh == u:
						out.append(kh)
						i += L
						done = True
						break
				if done:
					break
		if done:
			continue
		c = cons[i]
		if last:
			if c == 'य' and i > 0 and rng.random() < 0.3 and out and out[-1].endswith('\\'):
				out[-1] = out[-1][:-1]
				out.append('Ø')
			else:
				out.append(pick(rng, FULL[c]))
		else:
			if c in HALF:
				out.append(pick(rng, HALF[c]))
			else:
				out.append(pick(rng, FULL[c]) + '\\')
		i += 1
	return ''.join(out)


def encWord(w, rng):
	w = N(w)
	keys = []
	i = 0
	n = len(w)
	while i < n:
		ch = w[i]
		if ch in DIGIT:
			keys.append(DIGIT[ch])
			i += 1
			continue
		if ch in PUNCT:
			keys.append(PUNCT[ch])
			i += 1
			continue
		if ch in VOWEL:
			k = VOWEL[ch]
			i += 1
			mods = ''
			while i < n and w[i] in MOD:
				mods += MOD[w[i]]
				i += 1
			keys.append(k + mods)
			continue
		if ch not in CONS:
			raise Skip(ch)
		# a consonant cluster
		cons = [ch]
		j = i + 1
		while j + 1 < n and w[j] == H and w[j + 1] in CONS:
			cons.append(w[j + 1])
			j += 2
		final_halant = j < n and w[j] == H
		if final_halant:
			if j + 1 < n and w[j + 1] == '‍':
				raise Skip('zwj')
			j += 1
		matra = ''
		if not final_halant and j < n and w[j] in MATRA or (j < n and w[j] == 'ि'):
			matra = w[j]
			j += 1
		mods = ''
		while j < n and w[j] in MOD:
			mods += w[j]
			j += 1
		if j < n and w[j] in ('़', '‌', '‍'):
			raise Skip('nukta/zw')
		i = j
		reph = len(cons) >= 2 and cons[0] == 'र'
		if reph:
			cons = cons[1:]
		rakar = len(cons) >= 2 and cons[-1] == 'र' and not final_halant
		if rakar:
			cons = cons[:-1]
		# the body
		if final_halant:
			if cons[-1] in HALF and not rakar:
				body = encCluster(cons[:-1], rng) if len(cons) > 1 else ''
				if len(cons) > 1:
					# encCluster made the last consonant full: redo with all half
					body = ''.join(pick(rng, HALF[c]) if c in HALF else pick(rng, FULL[c]) + '\\' for c in cons[:-1])
				body += pick(rng, HALF[cons[-1]])
			else:
				body = encCluster(cons, rng) + ('|' if rakar else '') + '\\'
		elif rakar:
			if cons == ['त']:
				body = 'q'
			elif cons == ['श']:
				body = '>'
			elif cons[-1] in ('ट', 'ठ', 'ड', 'ढ'):
				body = encCluster(cons, rng) + '«'
			elif cons == ['क'] and rng.random() < 0.4:
				body = 'qm'
			elif cons[-1] == 'त' and len(cons) > 1:
				body = encCluster(cons[:-1] + ['त'], rng)[:-1] + 'q' if encCluster(cons[:-1] + ['त'], rng).endswith('t') else encCluster(cons, rng) + '|'
			else:
				body = encCluster(cons, rng) + '|'
		elif cons == ['र'] and matra in ('ु', 'ू') and not reph:
			body = '?' if matra == 'ु' else '¿'
			matra = ''
		elif cons == ['ह'] and matra == 'ृ' and rng.random() < 0.5:
			body = 'Å'
			matra = ''
		elif cons == ['क', 'त'] and rng.random() < 0.4:
			body = 'Qm'
		else:
			body = encCluster(cons, rng)
		if body.endswith('\\') and matra:
			raise Skip('halant+matra')
		k = ''
		if matra == 'ि':
			k = 'l' + body
		else:
			k = body + (MATRA[matra] if matra else '')
		m = ''.join(MOD[x] for x in mods)
		if reph:
			if rng.random() < 0.5 or not matra or matra == 'ि':
				k = k + '{' + m
			else:
				# reph typed before the vowel sign (ug{] for गर्ने)
				mk = MATRA[matra]
				k = body + '{' + mk + m
		else:
			k += m
		keys.append(k)
	return ''.join(keys)


def useFont(font):
	"""Switch the encoder's keys to another font of the family (only keys verified for that font)."""
	global FONT
	FONT = font
	if font == 'kantipur':
		MOD['ँ'] = '“'  # F is ा in Kantipur
	elif font in ('fontasy', 'pcs'):
		MOD['ँ'] = '¤'
	if font in ('kantipur', 'fontasy'):
		# X is हृ in these fonts; Î and ‹ are other letters in Kantipur
		HALF['ह'] = 'x\\'
		CONJ[:] = [(u, k) for u, k in CONJ if u not in ('ङ्ख', 'ङ्घ')]
	if font == 'fontasy':
		# digits are digits, Shift+digits are the letters, ' is ू and " is ु
		DIGIT.update(dict(zip('०१२३४५६७८९', '0123456789')))
		dk = dict(zip('1234567890', '!@#$%^&*()'))
		sub = lambda k: ''.join(dk.get(c, c) for c in k)
		for u in list(FULL):
			FULL[u] = [sub(x) for x in FULL[u]] if isinstance(FULL[u], list) else sub(FULL[u])
		for u in list(HALF):
			HALF[u] = [sub(x) for x in HALF[u]] if isinstance(HALF[u], list) else sub(HALF[u])
		for i, (u, k) in enumerate(CONJ):
			CONJ[i] = (u, [sub(x) for x in k] if isinstance(k, list) else sub(k))
		MATRA['ु'], MATRA['ू'] = '"', "'"


FONT = 'preeti'


def nepaliWords():
	data = json.loads(zlib.decompress(open('addon/globalPlugins/nepaliReader/nepaliWords.dat', 'rb').read()).decode('utf-8'))
	return sorted(w for w in data['stems'] if w and all('ऀ' <= c <= 'ॿ' for c in w))


def main():
	args = sys.argv[1:]
	show = 40
	if '--show' in args:
		show = int(args[args.index('--show') + 1])
	nmax = int(args[0]) if args and args[0].isdigit() else 0
	if '--font' in args:
		useFont(args[args.index('--font') + 1])
	rng = random.Random(11)
	words = nepaliWords()
	if nmax:
		words = rng.sample(words, min(nmax, len(words)))
	bad = []
	skipped = collections.Counter()
	tested = 0
	for w in words:
		try:
			keys = encWord(w, rng)
		except Skip as e:
			skipped[str(e)] += 1
			continue
		tested += 1
		got = N(LF.convert(keys, FONT))
		if got != N(w):
			bad.append((w, keys, got))
	print('tested', tested, 'bad', len(bad), 'skipped', sum(skipped.values()), dict(skipped.most_common(6)))
	for w, k, g in bad[:show]:
		print('  want %-16s keys %-18r got %s' % (w, k, g))
	if '--lines' in args:
		# whole lines, as the detector sees them when the font is unknown
		import detector as D
		import neLexicon
		neLexicon.load()
		D.loadDictionary()
		pool = [w for w in words if len(w) >= 2]
		nl = int(args[args.index('--lines') + 1])
		missed = []
		wrongw = collections.Counter()
		for _ in range(nl):
			ws = rng.sample(pool, rng.randint(1, 8))
			try:
				ks = [encWord(w, rng) for w in ws]
			except Skip:
				continue
			line = ' '.join(ks)
			got = D.convertMixed(line, LF.preetiFamilyToUnicode)
			gw = got.split(' ')
			if N(got) != N(' '.join(ws)):
				missed.append((' '.join(ws), line, got))
				if len(gw) == len(ws):
					for a, b, k in zip(ws, gw, ks):
						if N(a) != N(b):
							wrongw[(a, k, b)] += 1
		print('lines', nl, 'not fully converted', len(missed))
		for x in missed[:show]:
			print('  want %s\n   keys %s\n   got  %s' % x)
		print('words left wrong in lines:', len(wrongw))
		for (a, k, b), c in wrongw.most_common(show):
			print('   %-14s %-14r -> %s' % (a, k, b))
	return bad


if __name__ == '__main__':
	main()
