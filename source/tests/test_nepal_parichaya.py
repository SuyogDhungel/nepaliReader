# Nepal Parichaya, 12th edition (Department of Information and Broadcasting, 2081): a Preeti book
# made in InDesign, read in Chrome with the PDF file found. Lines, arrow keys (one key at a time),
# Shift+Arrow selections and the "selected ..." NVDA says when focus comes back to the PDF must all
# read the page as printed.
# Run from the source folder with NEPALI_TEST_BOOK set to the PDF
# ("NepaliReader test PDFs\nepal-parichaya-12th-edition-2081.pdf"):
#   python tests/test_nepal_parichaya.py
import os
import sys
import tempfile
import time
import types

PDF = os.environ.get('NEPALI_TEST_BOOK', '')
if not os.path.isfile(PDF):
	print('skip: set NEPALI_TEST_BOOK to nepal-parichaya-12th-edition-2081.pdf')
	sys.exit(0)
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, 'tests/fakenvda')
import setup_fake as F  # noqa: E402
sys.path.insert(0, 'addon/globalPlugins')
cfg = tempfile.mkdtemp(prefix='nr_np_')
F.mod('globalVars', appArgs=types.SimpleNamespace(configPath=cfg))
os.environ['HOME'] = os.path.join(cfg, 'home')
import nepaliReader as NR  # noqa: E402
import speech.speech as SS  # noqa: E402
from nepaliReader import pdfLocate  # noqa: E402

pdfLocate.readPdf = lambda loc, maxBytes=0: open(PDF, 'rb').read()
p = NR.GlobalPlugin()
while not p._ready:
	time.sleep(0.05)
F.state['app'] = 'chrome'
URL = 'https://daobardiya.moha.gov.np/upload/x/files/Nepal_Parichaya_12th_edition_2081_website_Final.pdf'
OBJ = types.SimpleNamespace(documentConstantIdentifier=URL, rootNVDAObject=types.SimpleNamespace(windowClassName='Chrome_RenderWidgetHostHWND', appModule=types.SimpleNamespace(appName='chrome')), treeInterceptor=None, appModule=types.SimpleNamespace(appName='chrome'))


class Info:
	"""A piece of Chrome's text of the page, with Chrome's units (ICU words: a run of letters, or one
	mark, with the spaces after it)."""

	def __init__(s, full, start, end=None):
		s.full = full
		s.start = start
		s.end = start + 1 if end is None else end
		s.obj = OBJ

	def copy(s):
		return Info(s.full, s.start, s.end)

	def expand(s, unit):
		f = s.full
		if unit == 'line':
			s.start, s.end = 0, len(f)
		elif unit == 'word':
			a = s.start
			if f[a].isalnum():
				while a > 0 and f[a - 1].isalnum():
					a -= 1
				b = s.start
				while b < len(f) and f[b].isalnum():
					b += 1
			else:
				b = a + 1
			while b < len(f) and f[b] in ' \t\r\n':
				b += 1
			s.start, s.end = a, b
		else:
			s.end = s.start + 1

	def collapse(s, end=False):
		if end:
			s.start = s.end
		else:
			s.end = s.start

	@property
	def isCollapsed(s):
		return s.start == s.end

	def setEndPoint(s, other, which):
		if which == 'endToStart':
			s.end = other.start
		elif which == 'startToStart':
			s.start = other.start
		elif which == 'startToEnd':
			s.start = other.end
		else:
			s.end = other.end

	def move(s, unit, n, endPoint=None):
		s.start += n
		s.end = s.start + 1
		return n if 0 <= s.start < len(s.full) else 0

	def compareEndPoints(s, other, which):
		a = s.start if which.startswith('start') else s.end
		b = other.start if which.endswith('Start') else other.end
		return (a > b) - (a < b)

	@property
	def text(s):
		return s.full[s.start:s.end]

	boundingRects = []

	def getTextWithFields(s, fc=None):
		return [F.FieldCommand('formatChange', F.FormatField({'font-name': 'sans-serif'})), s.full[s.start:s.end]]


def said(info, unit):
	seq = [x for x in next(SS.getTextInfoSpeech(info, unit=unit)) if isinstance(x, str)]
	return ''.join(x for x in p._filterSpeechSequence(seq) if isinstance(x, str)).strip()


F.state['title'] = 'Nepal_Parichaya_12th_edition_2081_website_Final.pdf - Google Chrome'
F.state['fg'] += 1
said(Info('x', 0), 'line')
t0 = time.time()
while time.time() - t0 < 600:
	st = p._pdfs.get_(p._foregroundKey())
	if st and st.status in ('ready', 'none') and (st.full or st.status == 'none'):
		break
	time.sleep(0.2)
print('index %s in %.0f s' % (st.status if st else None, time.time() - t0))

failures = 0


def check(name, got, want):
	global failures
	ok = got == want
	if not ok:
		failures += 1
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))


# lines as Chrome gives them, and as the book prints them
for chrome, printed in [
	('k"0f{ kl/dflh{t ;+:s/0f M @)^( j}zfv\r\n', 'पूर्ण परिमार्जित संस्करण : २०६९ वैशाख'),
	('t];|f] ;+:s/0f M @)&@ j}zfv\r\n', 'तेस्रो संस्करण : २०७२ वैशाख'),
	(';jf{lwsf/© M ;"rgf tyf k|;f/0f ljefu\r\n', 'सर्वाधिकार© : सूचना तथा प्रसारण विभाग'),
	("‘g]kfn kl/ro’ k':tsn] xfnsf] :j?k k|fKt u/sf] ] xf]. o;sf ;fy} oxfFsf] h}ljs, \r\n", '‘नेपाल परिचय’ पुस्तकले हालको स्वरुप प्राप्त गरेको हो । यसका साथै यहाँको जैविक,'),
	(';of}“ y\'“uf km"nsf xfdL Pp6} dfnf g]kfnL\r\n', 'सयौँ थुँगा फूलका हामी एउटै माला नेपाली'),
	('cu|ufdL /fi6« xfd|f] ho ho g]kfn .kl/dflh{t afx|f}“ ;+:s/0faf/]\r\n', 'अग्रगामी राष्ट्र हाम्रो जय जय नेपाल । परिमार्जित बाह्रौँ संस्करणबारे'),
	("ljifox¿ ;d]6]/ d'n'ssf] ;du| kIfsf ;DaGwdf ;ª\\lIfKt hfgsf/L k|bfg ug]{ p2]Zon]\r\n", 'विषयहरू समेटेर मुलुकको समग्र पक्षका सम्बन्धमा सङ्क्षिप्त जानकारी प्रदान गर्ने उद्देश्यले'),
	('xfn;Ddsf] cBfjlws ;"rgf, tYof+s / ljj/0fx¿ ;d]t ;d]6\\g] k|of; ul/Psf] 5 . \r\n', 'हालसम्मको अद्यावधिक सूचना, तथ्यांक र विवरणहरू समेत समेट्ने प्रयास गरिएको छ ।'),
	('k|sfzs M g]kfn ;/sf/\r\n', 'प्रकाशक : नेपाल सरकार'),
]:
	check('line ' + printed[:30], said(Info(chrome, 0, len(chrome)), 'line'), printed)

# the words of a long paragraph are not run together (InDesign's tight lines)
idx = p._pdfIndex(OBJ)
text = ' '.join((f if f is not None else k) for f, a, e, k in idx.words)
for phrase in ['मुक्तिनाथ हिन्दू तथा बौद्धमार्गीहरूको', 'नेपालको ऐतिहासिक, भौगोलिक, धार्मिक, सांस्कृतिक, आर्थिक, प्रशासनिक, राजनीतिक', 'विषयहरू समेटेर मुलुकको समग्र', 'खारेज']:
	check('words apart: ' + phrase[:30], phrase in text, True)
check('no colon read as visarga', ' ः ' in text, False)

# arrow keys: every key says something, and what it adds to the word
LINE = 't];|f] ;+:s/0f M @)&@ j}zfv\r\nrf}yf] ;+:s/0f M @)&# j}zfv\r\n'
got = [p._selectionText(Info(LINE, a, a + 1)) for a in range(29)]
want = ['त', 'े', 'स', '्र', 'ा', 'ो', ' ', 'स', 'ं', 'स्', 'क', 'र', 'ण्', 'ण', ' ', ':', ' ', '२', '०', '७', '२', ' ', 'व', 'ै', 'श', 'ा', 'ख']
check('selecting one key at a time', got[:len(want)], want)
LINE2 = 'k"0f{ kl/dflh{t ;+:s/0f M @)^( j}zfv\r\n'
check('reph key says र्', [p._selectionText(Info(LINE2, a, a + 1)) for a in (4, 13)], ['र्', 'र्'])
check('no key is silent', [LINE[a] for a in range(27) if LINE[a] != ' ' and not got[a].strip()], [])
for a, b, want in [(1, 33, 'ेस्रो संस्करण : २०७२ वैशाख\r\nचौथ'), (10, 14, 'करण'), (8, 12, 'ंस्कर'), (29, 35, 'चौथो')]:
	check('selection %r' % LINE[a:b], p._selectionText(Info(LINE, a, b)), want)

# what NVDA says when focus comes back to the PDF with text selected
import api  # noqa: E402
api.getFocusObject = lambda: OBJ
for raw, want in [('];|f] ;+:s/0f M @)&@ j}zfv\r\nrf}yf]', 'selected ेस्रो संस्करण : २०७२ वैशाख चौथो'),
		('ho ho g]kfn', 'selected जय जय नेपाल'), ('s/0f', 'selected करण'),
		('जय जय नेपाल', 'selected जय जय नेपाल'), ('www.doib.gov.np', 'selected www.doib.gov.np')]:
	check('selected on focus: ' + raw[:20], ''.join(SS._getSelectionMessageSpeech('selected %s', raw)), want)

p.terminate()
print('\n%d failed' % failures if failures else '\nall passed')
sys.exit(1 if failures else 0)
