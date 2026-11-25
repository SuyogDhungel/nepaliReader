# Some PDF makers draw a line from its last letter to its first ("Microsoft Print to PDF" reprinting
# a PDF, Word for "(क)"): every letter is at its place on the page, only the order in the file is
# backwards. The add-on turns such runs round, for any font, and finds the viewer's text of them
# (Chrome puts the letters in order but each sign without width one letter late: मरो/े for मेरो/).
# Run from the source folder: python tests/test_backwards_runs.py
# NEPALI_TEST_LAWS=<laws folder> also checks every line of two real laws drawn backwards;
# NEPALI_TEST_FORM=<a one-page PDF made by Microsoft Print to PDF with Preeti text> reads its lines as
# Chrome gives them (needs pypdfium2, the PDF engine of Chrome).
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


def pdfOf(lines):
	"""A one-page PDF in Courier (every letter 0.6 em wide). lines: (y, text, backwards, spacing):
	the letters at their places, drawn left to right or right to left."""
	ops = []
	for y, text, backwards, spacing in lines:
		cells = [(72 + i * (7.2 + spacing), ch) for i, ch in enumerate(text)]
		if backwards:
			cells.reverse()
		for x, ch in cells:
			if ch != ' ' or not spacing:
				ops.append('BT /F1 12 Tf 1 0 0 1 %.2f %d Tm (%s) Tj ET' % (x, y, ch.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')))
	stream = '\n'.join(ops).encode('latin-1')
	objs = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
		b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
		b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream',
		b'<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>']
	out = b'%PDF-1.4\n'
	offs = []
	for n, o in enumerate(objs, 1):
		offs.append(len(out))
		out += b'%d 0 obj\n' % n + o + b'\nendobj\n'
	x = len(out)
	out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offs)
	out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, x)
	return out


def words(data):
	idx = pdfText.DocIndex.build(data, detector=None, isWord=None, timeLimit=60)
	return [k for f, a, e, k in idx.words], idx


text = 'nepal reader reads it'
forward, i1 = words(pdfOf([(700, text, False, 0)]))
backward, i2 = words(pdfOf([(700, text, True, 0)]))
check('a line drawn left to right', forward, text.split())
check('the same line drawn right to left reads the same', backward, text.split())
check('...and is known to be drawn backwards', (i1.reversedRuns, i2.reversedRuns > 0), (0, True))
spacedF, _i = words(pdfOf([(700, 'TITLE OF ACT', False, 2.0)]))
spacedB, _i = words(pdfOf([(700, 'TITLE OF ACT', True, 2.0)]))
check('a title with spaced-out letters drawn right to left reads as drawn left to right', spacedB, spacedF)
short, _i = words(pdfOf([(700, '(k) and', True, 0), (680, 'more text here', False, 0)]))
check('a short run "(k)" drawn right to left (as Word does)', short, ['(k)', 'and', 'more', 'text', 'here'])
two, _i = words(pdfOf([(700, 'first line', True, 0), (680, 'second line', True, 0)]))
check('two lines, each drawn right to left', two, ['first', 'line', 'second', 'line'])

# real laws, every line drawn backwards: the same words (Kalimati made by Word; Preeti)
folder = os.environ.get('NEPALI_TEST_LAWS', '')
if os.path.isdir(folder):
	import glyphRefs
	glyphRefs.load()
	for name, least in (('nepali-law-बालबालिका-सम्बन्धी-ऐन-२०७५-supremecourt.pdf', 99.0), ('nepali-law-राष्ट्रिय-निकुञ्ज-तथा-वन्यजन्तु-संरक्षण-ऐन-२०२९-snp.pdf', 97.0)):
		path = os.path.join(folder, name)
		if not os.path.isfile(path):
			continue
		cap = []
		orig = pdfText._words
		pdfText._words = lambda gl, page: (cap.append((list(gl), page)), orig(gl, page))[1]
		pdfText.DocIndex.build(open(path, 'rb').read(), detector=None, isWord=None, timeLimit=300, maxPages=12)
		pdfText._words = orig
		same = total = 0
		for gl, page in cap:
			want = [''.join(g[0].text(g[1]) or '' for g in w.glyphs) for w in orig(gl, page)]
			groups = []
			for n, g in enumerate(gl):
				if groups and abs(g[3] - gl[groups[-1][-1]][3]) <= 0.3 * (g[4] or 1):
					groups[-1].append(n)
				else:
					groups.append([n])
			for grp in groups:
				if len(grp) < 4:
					continue
				total += 1
				g2 = list(gl)
				for i, g in zip(grp, reversed([gl[i] for i in grp])):
					g2[i] = g
				same += [''.join(g[0].text(g[1]) or '' for g in w.glyphs) for w in orig(g2, page)] == want
		rate = 100.0 * same / max(1, total)
		check('%s: lines drawn backwards read the same (%.1f%% of %d, at least %.0f%%)' % (name[:40], rate, total, least), rate >= least, True)
else:
	print('skip: set NEPALI_TEST_LAWS to check real laws drawn backwards')

form = os.environ.get('NEPALI_TEST_FORM', '')
if os.path.isfile(form):
	try:
		import pypdfium2 as pdfium
	except ImportError:
		pdfium = None
		print('skip: pypdfium2 is not installed')
	if pdfium is not None:
		import neLexicon
		neLexicon.load()
		import detector
		detector.loadDictionary()
		import glyphRefs
		glyphRefs.load()
		idx = pdfText.DocIndex.build(open(form, 'rb').read(), detector=detector, isWord=neLexicon.isWord, timeLimit=120)
		idx.prepare()
		read = total = 0
		for line in pdfium.PdfDocument(form)[0].get_textpage().get_text_range().splitlines():
			if len(line.split()) < 3:
				continue
			total += 1
			got = idx.lookup(line)
			read += bool(got) and all(ok for pc, ok in got)
		rate = 100.0 * read / max(1, total)
		check('lines as Chrome shows them are read (%.1f%% of %d, at least 85%%)' % (rate, total), rate >= 85.0, True)
else:
	print('skip: set NEPALI_TEST_FORM to read a PDF made by Microsoft Print to PDF')

print('\n%d failed' % failures if failures else '\nall passed')
sys.exit(1 if failures else 0)
