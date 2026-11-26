# Character, word and line reading of a PDF agree, also where the viewer's text differs from the
# PDF's (characters are read in the document's order, the order line reading says them): text of the viewer itself in front of a line (Chrome's "Finished loading PDF"), a word the
# viewer cuts in pieces or gives in another order, a form's fill-in line drawn through a label, and
# the keys of a Preeti word one by one (the short i key, a vowel key after the nasal sign key).
# Run from the source folder: python tests/test_nav_consistency.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'addon', 'globalPlugins', 'nepaliReader'))
import pdfText  # noqa: E402

failures = 0


def check(name, got, want):
	global failures
	ok = got == want
	if not ok:
		failures += 1
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))


def pdfOf(lines, font='Preeti'):
	"""A one-page PDF, every letter in its own place (Courier widths) in a font named `font`."""
	ops = []
	for y, text in lines:
		for i, ch in enumerate(text):
			if ch != ' ':
				ops.append('BT /F1 12 Tf 1 0 0 1 %.2f %d Tm (%s) Tj ET' % (72 + i * 7.2, y, ch.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')))
	stream = '\n'.join(ops).encode('cp1252')
	objs = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
		b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
		b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream',
		b'<< /Type /Font /Subtype /Type1 /BaseFont /' + font.encode() + b' /Encoding /WinAnsiEncoding >>']
	out = b'%PDF-1.4\n'
	offs = []
	for n, o in enumerate(objs, 1):
		offs.append(len(out))
		out += b'%d 0 obj\n' % n + o + b'\nendobj\n'
	x = len(out)
	out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offs)
	out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, x)
	return out


def keys(idx, line, word):
	o = line.index(word)
	return [idx.charAt(line, i, 1) for i in range(o, o + len(word))]


def byChar(idx, line):
	"""What moving along the line character by character says, key by key (spaces left out)."""
	return [idx.charAt(line, i, 1) for i, ch in enumerate(line) if pdfText.keyOf(ch)]


idx = pdfText.DocIndex.build(pdfOf([(700, 'a}+lsË l:y ub{5f+} dxf]bo')]), detector=None, isWord=None, timeLimit=60)
line = 'a}+lsË l:y ub{5f+} dxf]bo'
check('the short i key says ि, the letter after it says the letter with it', keys(idx, line, 'a}+lsË'), ['ब', 'ै', 'ं', 'ि', 'कि', 'ङ्ग'])
check('...also before a cluster: the half letter says itself, the cluster says itself with ि', keys(idx, line, 'l:y'), ['ि', 'स्', 'स्थि'])
check('a vowel key after the nasal sign key says only the vowel', keys(idx, line, '5f+}'), ['छ', 'ा', 'ं', 'ौ'])

viewer = 'Finished loading PDF' + line
check("the viewer's own text in front of the first line is not looked for in the PDF", idx.charAt(viewer, 3), None)
check('...and the rest of the line is read from the PDF', keys(idx, viewer, 'a}+lsË'), ['ब', 'ै', 'ं', 'ि', 'कि', 'ङ्ग'])
check('...word by word as well', ''.join(pc for pc, ok in idx.spanAt(viewer, viewer.index('dxf]bo'), 6)), 'महोदय')

# a form drawn backwards (zero-width signs in the viewer's text at other places)
form = pdfText.DocIndex.build(pdfOf([(700, 'kl/ro kq =========='), (680, 'kfgf g+=-!_ ljifo k|of]u ug{'), (660, 'cfjZos ljifo')]),
	detector=None, isWord=None, timeLimit=60)
form.zeroKeys = ['+', ']', '{', '}']
shown = 'k ===== l/rokq ====='
got = form.lookup(shown)
check('a label with the fill-in line drawn through it reads as the label, then the dots', ' '.join(pc for pc, ok in got) if got and all(ok for pc, ok in got) else got,
	'परिचय पत्र ..........')
check('...its first letter alone (before the dots) is the label\'s first letter', form.charAt(shown, 0), 'प')
check('...and by character the label, then the dots, as line reading says it', byChar(form, shown), byChar(form, 'kl/ro kq =========='))
shown = 'kfgf g -!_ =+ ljifo'
got = form.lookup(shown)
check('a number\'s brackets the viewer puts before its signs ("g -!_ =+" for g+=-!_)', ' '.join(pc for pc, ok in got) if got and all(ok for pc, ok in got) else got,
	'पाना नं.(१) विषय')
check('...by character in the order line reading says it (नं.(१))', byChar(form, shown), byChar(form, 'kfgf g+=-!_ ljifo'))
check('two words in another order are not the same line (another column first)', form._findShuffled(pdfText.matchKey('ljifo cfjZos')), -1)
shown = 'ko| fu] ug{'
got = form.lookup(shown)
check('a word the viewer cuts in two pieces ("ko| fu]" for k|of]u) reads as the word', ' '.join(pc for pc, ok in got) if got and all(ok for pc, ok in got) else got,
	'प्रयोग गर्न')
check('...and by character as the word is written', byChar(form, shown), byChar(form, 'k|of]u ug{'))

print('\n%d failed' % failures if failures else '\nall passed')
sys.exit(1 if failures else 0)
