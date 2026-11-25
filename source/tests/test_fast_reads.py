# Reading a PDF in Chrome asks the document as little as possible: every call into the browser
# (a line's text, the line around a place) goes to another process and was what made arrow keys
# slow (10 to 17 calls a read in 2.2.0). On average a line or word read asks at most 5 things, a
# character 6 (a line that is in the document more than once also asks for the lines around it, a
# key not found in the PDF for the characters beside it). And the fast way reads
# exactly what the slow way read: every line, character, word and selection of three real PDFs
# is read both with offsets (as Chrome's browse mode gives them) and without, and must be the same.
# Run from the source folder: NEPALI_TEST_PDFS=<folder with the PDFs of test_real_reads> python tests/test_fast_reads.py
# (NEPALI_TEST_BOOK=<nepal-parichaya-12th-edition-2081.pdf> adds the Preeti book)
import collections
import json
import os
import sys
import tempfile
import time
import types

folder = os.environ.get('NEPALI_TEST_PDFS', '')
book = os.environ.get('NEPALI_TEST_BOOK', '')
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
rr = json.load(open('tests/real_reads_chrome_pdfjs.json', encoding='utf-8'))['pdfs']
DOCS = []
for name, n in (('बालबालिका-सम्बन्धी-ऐन-२०७५.pdf', 60), ('NPWC Act 2029.pdf', 20)):
	if os.path.isfile(os.path.join(folder, name)):
		DOCS.append((name, os.path.join(folder, name), ''.join(g + '\r\n' for g, w in rr[name][:n])))
if os.path.isfile(book):
	DOCS.append(('Nepal Parichaya', book,
		'k"0f{ kl/dflh{t ;+:s/0f M @)^( j}zfv\r\nt];|f] ;+:s/0f M @)&@ j}zfv\r\n;jf{lwsf/© M ;"rgf tyf k|;f/0f ljefu\r\n\r\n'
		"‘g]kfn kl/ro’ k':tsn] xfnsf] :j?k k|fKt u/sf] ] xf]. o;sf ;fy} oxfFsf] h}ljs, \r\n"
		'cu|ufdL /fi6« xfd|f] ho ho g]kfn .kl/dflh{t afx|f}“ ;+:s/0faf/]\r\nPage 6\r\n'
		"ljifox¿ ;d]6]/ d'n'ssf] ;du| kIfsf ;DaGwdf ;ª\\lIfKt hfgsf/L k|bfg ug]{ p2]Zon]\r\nPrint\r\n"))
if not DOCS:
	print('skip: set NEPALI_TEST_PDFS (and NEPALI_TEST_BOOK) to the test PDFs')
	sys.exit(0)

sys.path.insert(0, 'tests/fakenvda')
import setup_fake as F  # noqa: E402
sys.path.insert(0, 'addon/globalPlugins')
cfg = tempfile.mkdtemp(prefix='nr_fast_')
F.mod('globalVars', appArgs=types.SimpleNamespace(configPath=cfg))
os.environ['HOME'] = os.path.join(cfg, 'home')
import nepaliReader as NR  # noqa: E402
import speech.speech as SS  # noqa: E402
from nepaliReader import pdfLocate  # noqa: E402
import api  # noqa: E402

CUR = {}
pdfLocate.readPdf = lambda loc, maxBytes=0: open(CUR['pdf'], 'rb').read()
F.state['app'] = 'chrome'
CALLS = collections.Counter()


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


class _Base:
	"""Chrome's browse mode text: lines end with \\r\\n, a word is a run of letters (with the
	spaces after it), and every question asked is counted."""

	def __init__(s, start, end=None):
		s._set(start, start + 1 if end is None else end)
		s.obj = Doc.obj

	def copy(s):
		return s.__class__(*s._get())

	def expand(s, unit):
		CALLS['expand'] += 1
		f = Doc.text
		a, b = s._get()
		if unit == 'line':
			s._set(*lineBounds(a))
		elif unit == 'word':
			a = min(a, len(f) - 1)
			isw = lambda ch: ch.isalnum() or 'ऀ' <= ch <= 'ॿ'  # noqa: E731
			if isw(f[a]):
				while a > 0 and isw(f[a - 1]):
					a -= 1
				b = s._get()[0]
				while b < len(f) and isw(f[b]):
					b += 1
			else:
				b = a + 1
			while b < len(f) and f[b] in ' \t':
				b += 1
			s._set(a, b)
		else:
			s._set(a, a + 1)

	def collapse(s, end=False):
		a, b = s._get()
		s._set(b, b) if end else s._set(a, a)

	@property
	def isCollapsed(s):
		a, b = s._get()
		return a == b

	def setEndPoint(s, other, which):
		a, b = s._get()
		oa, ob = other._get()
		if which == 'endToStart':
			s._set(a, oa)
		elif which == 'startToStart':
			s._set(oa, b)
		elif which == 'startToEnd':
			s._set(ob, b)
		else:
			s._set(a, ob)

	def move(s, unit, n, endPoint=None):
		CALLS['move'] += 1
		pos = s._get()[0]
		moved = 0
		T = Doc.text
		for _ in range(abs(n)):
			if unit == 'line':
				a, b = lineBounds(pos)
				if n > 0:
					if b >= len(T):
						break
					pos = b
				else:
					if a == 0:
						break
					pos = lineBounds(a - 1)[0]
			else:
				q = pos + (1 if n > 0 else -1)
				if not 0 <= q < len(T):
					break
				pos = q
			moved += 1
		a, b = s._get()
		if endPoint == 'start':
			s._set(pos, b)
		elif endPoint == 'end':
			s._set(a, pos)
		else:
			s._set(pos, pos)
		return moved if n > 0 else -moved

	def compareEndPoints(s, other, which):
		a = s._get()[0] if which.startswith('start') else s._get()[1]
		b = other._get()[0] if which.endswith('Start') else other._get()[1]
		return (a > b) - (a < b)

	@property
	def text(s):
		CALLS['text'] += 1
		a, b = s._get()
		return Doc.text[a:b]

	boundingRects = []

	def getTextWithFields(s, fc=None):
		CALLS['getTextWithFields'] += 1
		a, b = s._get()
		return [F.FieldCommand('formatChange', F.FormatField({'font-name': 'sans-serif'})), Doc.text[a:b]]


class WithOffsets(_Base):
	def _set(s, a, b):
		s._startOffset, s._endOffset = a, b

	def _get(s):
		return s._startOffset, s._endOffset


class WithoutOffsets(_Base):
	def _set(s, a, b):
		s._a, s._b = a, b

	def _get(s):
		return s._a, s._b


p = NR.GlobalPlugin()
while not p._ready:
	time.sleep(0.05)


def said(info, unit):
	seq = [x for x in next(SS.getTextInfoSpeech(info, unit=unit)) if isinstance(x, str)]
	return ''.join(x for x in p._filterSpeechSequence(seq) if isinstance(x, str))


failures = 0
LIMITS = {'line': (5, 8), 'char': (6, 10), 'word': (5, 6)}  # (average, most)


def check(name, ok, detail=''):
	global failures
	if not ok:
		failures += 1
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     ' + detail))


for n, (name, pdf, text) in enumerate(DOCS):
	CUR['pdf'] = pdf
	Doc.text = text
	Doc.obj = types.SimpleNamespace(documentConstantIdentifier='https://example.gov.np/files/doc%d.pdf' % n,
		rootNVDAObject=types.SimpleNamespace(windowClassName='Chrome_RenderWidgetHostHWND', appModule=types.SimpleNamespace(appName='chrome')),
		treeInterceptor=None, appModule=types.SimpleNamespace(appName='chrome'))
	api.getFocusObject = lambda: Doc.obj
	F.state['title'] = 'doc%d.pdf - Google Chrome' % n
	F.state['fg'] = 200 + n
	said(WithOffsets(0, 3), 'line')
	t0 = time.time()
	while time.time() - t0 < 900:
		st = p._pdfs.get_(p._foregroundKey())
		if st and st.status in ('ready', 'none') and (st.full or st.status == 'none') and (st.index is None or st.index._byKey is not None):
			break
		time.sleep(0.2)
	lines = []
	pos = 0
	while pos < len(text):
		a, b = lineBounds(pos)
		lines.append((a, b))
		pos = b
	reads = [('line', a, b, 'line') for a, b in lines]
	for a, b in lines[:12]:
		reads += [('char', i, i + 1, 'character') for i in range(a, b)]
		i = a
		while i < b - 1:
			w = WithOffsets(i)
			w.expand('word')
			reads.append(('word',) + w._get() + ('word',))
			i = max(w._get()[1], i + 1)
		mid = a + (b - a) // 3
		reads += [('select', mid, min(len(text), b + 6), None), ('select', a, b, None)]
	differ = []
	most = collections.Counter()
	total = collections.Counter()
	count = collections.Counter()
	for kind, a, b, unit in reads:
		got = []
		for cls in (WithoutOffsets, WithOffsets):
			CALLS.clear()
			info = cls(a, b)
			got.append(p._selectionText(info) if unit is None else said(info, unit))
			if cls is WithOffsets:
				most[kind] = max(most[kind], sum(CALLS.values()))
				total[kind] += sum(CALLS.values())
				count[kind] += 1
		if got[0] != got[1]:
			differ.append((kind, text[a:b], got[0], got[1]))
	check('%s: %d reads the same with offsets and without' % (name, len(reads)), not differ, repr(differ[:3]))
	for kind, (avgLimit, limit) in LIMITS.items():
		avg = total[kind] / max(1, count[kind])
		check('%s: a %s read asks the document %.1f times on average (at most %d), never more than %d (%d)' % (name, kind, avg, avgLimit, limit, most[kind]), avg <= avgLimit and most[kind] <= limit)

p.terminate()
print('\n%d failed' % failures if failures else '\nall passed')
sys.stdout.flush()
os._exit(1 if failures else 0)
