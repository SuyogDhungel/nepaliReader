# Every way of reading a PDF line says the same: line reading, word by word (Ctrl+Arrow), the word
# selected, the whole line selected, and character by character (Arrow) with its selection. A
# word of the PDF that the viewer shows in another order (a run drawn backwards: "ko| fu]" for
# प्रयोग) is read in the document's order in every one of them, a space the viewer put inside a
# word is no stop of its own, and no letter of a Nepali word is said as its Preeti key.
# Read as NVDA reads Chrome's PDF viewer (a fake NVDA; Chrome's text from PDFium, its PDF engine).
# (The two acts are read here through PDFium's text, which damages some of their lines; Chrome's
# "PDF Viewer" extension gives them whole: test_real_reads.)
# Run from the source folder, with any of:
#   NEPALI_TEST_FORM=<a PDF made by Microsoft Print to PDF with Preeti text>
#   NEPALI_TEST_PDFS=<folder with the PDFs of test_real_reads>
#   NEPALI_TEST_BOOK=<nepal-parichaya-12th-edition-2081.pdf>
# python tests/test_reading_modes.py
import os
import re
import sys
import tempfile
import time
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
DOCS = []
form = os.environ.get('NEPALI_TEST_FORM', '')
if os.path.isfile(form):
	DOCS.append(('a PDF drawn backwards', form, 100, 95.0))
folder = os.environ.get('NEPALI_TEST_PDFS', '')
for name, least in (('बालबालिका-सम्बन्धी-ऐन-२०७५.pdf', 85.0), ('NPWC Act 2029.pdf', 80.0)):
	if os.path.isfile(os.path.join(folder, name)):
		DOCS.append((name, os.path.join(folder, name), 40, least))
book = os.environ.get('NEPALI_TEST_BOOK', '')
if os.path.isfile(book):
	DOCS.append(('Nepal Parichaya', book, 40, 90.0))
try:
	import pypdfium2 as pdfium
except ImportError:
	pdfium = None
if not DOCS or pdfium is None:
	print('skip: set NEPALI_TEST_FORM, NEPALI_TEST_PDFS or NEPALI_TEST_BOOK (and install pypdfium2)')
	sys.exit(0)

sys.path.insert(0, 'tests/fakenvda')
import setup_fake as F  # noqa: E402
sys.path.insert(0, 'addon/globalPlugins')
cfg = tempfile.mkdtemp(prefix='nr_modes_')
F.mod('globalVars', appArgs=types.SimpleNamespace(configPath=cfg))
os.environ['HOME'] = os.path.join(cfg, 'home')
import virtualBuffers  # noqa: E402


class Doc:
	text = ''
	obj = None


def lineBounds(pos):
	t = Doc.text
	pos = min(pos, len(t) - 1)
	a = t.rfind('\n', 0, pos) + 1 if pos > 0 else 0
	if t[pos] == '\n':
		a = t.rfind('\n', 0, pos) + 1
	b = t.find('\n', pos)
	return a, (len(t) if b < 0 else b + 1)


def viewerWords(ti, offset):
	"""NVDA's own word (Uniscribe): a run of letters and digits, or one other character."""
	a, b = ti._getLineOffsets(offset)
	t = ti._getTextRange(a, b)
	r = offset - a
	for m in re.finditer(r'\w+\s*|[^\w\s]\s*|\s+', t):
		if m.start() <= r < m.end():
			return (a + m.start(), a + m.end())
	return (offset, offset + 1)


VB = virtualBuffers.VirtualBufferTextInfo
VB._getWordOffsets = viewerWords
VB._getCharacterOffsets = lambda ti, offset: (offset, offset + 1)


class TI(VB):
	"""Chrome's browse mode text, with offsets (the add-on's word and character patches apply)."""

	def __init__(s, a, b=None):
		s._startOffset, s._endOffset = a, (a + 1 if b is None else b)
		s.obj = Doc.obj

	def _getLineOffsets(s, o):
		return lineBounds(o)

	def _getTextRange(s, a, b):
		return Doc.text[a:b]

	def copy(s):
		return TI(s._startOffset, s._endOffset)

	def expand(s, unit):
		a = s._startOffset
		if unit == 'line':
			s._startOffset, s._endOffset = lineBounds(a)
		elif unit == 'word':
			s._startOffset, s._endOffset = s._getWordOffsets(a)
		else:
			s._startOffset, s._endOffset = s._getCharacterOffsets(a)

	def collapse(s, end=False):
		if end:
			s._startOffset = s._endOffset
		else:
			s._endOffset = s._startOffset

	@property
	def isCollapsed(s):
		return s._startOffset == s._endOffset

	def setEndPoint(s, other, which):
		if which == 'endToStart':
			s._endOffset = other._startOffset
		elif which == 'startToStart':
			s._startOffset = other._startOffset
		elif which == 'startToEnd':
			s._startOffset = other._endOffset
		else:
			s._endOffset = other._endOffset

	def move(s, unit, n, endPoint=None):
		pos = s._startOffset
		moved = 0
		for _ in range(abs(n)):
			if unit == 'line':
				a, b = lineBounds(pos)
				if n > 0:
					if b >= len(Doc.text):
						break
					pos = b
				else:
					if a == 0:
						break
					pos = lineBounds(a - 1)[0]
			else:
				get = s._getWordOffsets if unit == 'word' else s._getCharacterOffsets
				if n > 0:
					q = get(pos)[1]
					if q >= len(Doc.text):
						break
				else:
					if pos == 0:
						break
					q = get(pos - 1)[0]
				pos = q
			moved += 1
		s._startOffset = s._endOffset = pos
		return moved if n > 0 else -moved

	def compareEndPoints(s, other, which):
		a = s._startOffset if which.startswith('start') else s._endOffset
		b = other._startOffset if which.endswith('Start') else other._endOffset
		return (a > b) - (a < b)

	@property
	def text(s):
		return Doc.text[s._startOffset:s._endOffset]

	boundingRects = []

	def getTextWithFields(s, fc=None):
		return [F.FieldCommand('formatChange', F.FormatField({'font-name': 'sans-serif'})), Doc.text[s._startOffset:s._endOffset]]


import nepaliReader as NR  # noqa: E402
import speech.speech as SS  # noqa: E402
from nepaliReader import pdfLocate  # noqa: E402
import api  # noqa: E402

CUR = {}
pdfLocate.readPdf = lambda loc, maxBytes=0: open(CUR['pdf'], 'rb').read()
F.state['app'] = 'chrome'
p = NR.GlobalPlugin()
while not p._ready:
	time.sleep(0.05)


class CharacterModeCommand:
	pass


def said(info, unit):
	seq = [x for x in next(SS.getTextInfoSpeech(info, unit=unit)) if isinstance(x, str)]
	if unit == 'character':
		seq = [CharacterModeCommand()] + seq  # (NVDA says a character in character mode)
	return ''.join(x for x in p._filterSpeechSequence(seq) if isinstance(x, str))


DEVA = re.compile('[ऀ-ॿ]')
failures = 0


def check(name, ok, detail=''):
	global failures
	if not ok:
		failures += 1
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     ' + detail))


def lineProblems(a, b):
	"""What does not agree on the line a..b of the viewer's text (empty when all agree)."""
	probs = []
	line = ' '.join(said(TI(a, b), 'line').split())
	sel = ' '.join(p._selectionText(TI(a, b)).split())
	if sel != line:
		probs.append('selection %r' % sel[:120])
	words = []
	i = a
	while i < b - 2:
		w = TI(i)
		w.expand('word')
		ws, we = w._startOffset, w._endOffset
		got = said(w.copy(), 'word')
		if got.strip():
			words.append(' '.join(got.split()))
		if ' '.join(p._selectionText(w.copy()).split()) != ' '.join(got.split()):
			probs.append('word selected %r' % got.strip())
		if DEVA.search(got):
			# the characters of a Nepali word: never a Preeti key, never a stop on a space inside it
			inner = ws + len(Doc.text[ws:we].rstrip(' \t\xa0\r\n'))
			j = ws
			while j < inner:
				c = TI(j)
				c.expand('character')
				ch = said(c.copy(), 'character')
				if not Doc.text[c._startOffset:c._endOffset].strip():
					probs.append('a stop on a space inside %r' % got.strip())
				elif ch.isascii() and any(x.isalpha() for x in ch):
					probs.append('%r of %r said as a key' % (ch, got.strip()))
				if p._selectionText(c.copy()) != ch:
					probs.append('character selected %r, said %r' % (p._selectionText(c.copy()), ch))
				j = max(c._endOffset, j + 1)
		i = max(we, i + 1)
	if re.sub(r'\s+', '', ''.join(words)) != re.sub(r'\s+', '', line):
		# (the same text in the same order; a space more or less between two words is not counted)
		probs.append('words %r' % ' '.join(words)[:120])
	return line, probs


for n, (name, pdf, most, least) in enumerate(DOCS):
	CUR['pdf'] = pdf
	d = pdfium.PdfDocument(pdf)
	lines = []
	for i in range(len(d)):
		lines += d[i].get_textpage().get_text_range().splitlines()
		if len(lines) >= most:
			break
	Doc.text = 'Finished loading PDF' + ''.join(ln + '\r\n' for ln in lines[:most])
	Doc.obj = types.SimpleNamespace(documentConstantIdentifier='https://example.org/files/doc%d.pdf' % n,
		rootNVDAObject=types.SimpleNamespace(windowClassName='Chrome_RenderWidgetHostHWND', appModule=types.SimpleNamespace(appName='chrome')),
		treeInterceptor=None, appModule=types.SimpleNamespace(appName='chrome'))
	api.getFocusObject = lambda: Doc.obj
	F.state['title'] = 'doc%d.pdf - Google Chrome' % n
	F.state['fg'] = 300 + n
	said(TI(0, 3), 'line')
	t0 = time.time()
	while time.time() - t0 < 900:
		st = p._pdfs.get_(p._foregroundKey())
		if st and st.status in ('ready', 'none') and (st.full or st.status == 'none') and (st.index is None or st.index._byKey is not None):
			break
		time.sleep(0.2)
	same = total = 0
	shown = 0
	pos = 0
	while pos < len(Doc.text):
		a, b = lineBounds(pos)
		pos = b
		if not Doc.text[a:b].strip():
			continue
		total += 1
		line, probs = lineProblems(a, b)
		if not probs:
			same += 1
		elif shown < 3:
			shown += 1
			print('     differs: %s\n        %s' % (line[:90], '\n        '.join(x[:150] for x in probs[:3])))
	rate = 100.0 * same / max(1, total)
	check('%s: every way of reading says the same on %.1f%% of %d lines (at least %.0f%%)' % (name, rate, total, least), rate >= least)

p.terminate()
print('\n%d failed' % failures if failures else '\nall passed')
sys.stdout.flush()
os._exit(1 if failures else 0)
