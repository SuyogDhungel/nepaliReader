# A PDF read in Chrome through the "PDF Viewer" extension (PDF.js) and in Chrome's own viewer,
# and NVDA's speed while PDFs are read (mock NVDA, not Windows).
# Run from the source folder: python tests/test_chrome_pdf.py
# CHROME_PDF_TEST=<path of बालबालिका-सम्बन्धी-ऐन-२०७५.pdf> also reads the act itself as PDF.js shows it.
import json, os, sys, tempfile, threading, time, types, urllib.parse
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
cfg = tempfile.mkdtemp(prefix='nr_chromepdf_')
F.mod('globalVars', appArgs=types.SimpleNamespace(configPath=cfg))
os.environ['HOME'] = os.path.join(cfg, 'home')
os.makedirs(os.environ['HOME'], exist_ok=True)
import nepaliReader as NR, speech.speech as SS
from nepaliReader import pdfLocate, devanagariRepair, diag

failures = []


def check(name, got, want=True):
    ok = got == want
    print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '   got %r, want %r' % (got, want)))
    if not ok:
        failures.append(name)


print('== the PDF behind a viewer address')
ACT = 'बालबालिका-सम्बन्धी-ऐन-२०७५.pdf'
web = 'https://supremecourt.gov.np/web/assets/downloads/' + urllib.parse.quote(ACT)
check('PDF.js extension, a web PDF', pdfLocate._pathFromUrl('chrome-extension://oemmndcbldboiebfnladdacbdfmadadm/' + web), web)
check('PDF.js extension, older viewer.html?file=', pdfLocate._pathFromUrl('chrome-extension://oemmndcbldboiebfnladdacbdfmadadm/content/web/viewer.html?file=' + urllib.parse.quote(web, safe='')), web)
check("Chrome's own viewer ?src=", pdfLocate._pathFromUrl('chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/index.html?src=' + urllib.parse.quote(web, safe='')), web)
local = os.path.join(os.environ['HOME'], 'Downloads')
os.makedirs(local, exist_ok=True)
with open(os.path.join(local, ACT), 'wb') as f:
    f.write(b'%PDF-1.4\n' + b'0' * 2000)
check('PDF.js extension, a web PDF already in Downloads (its name %-encoded in the address)', pdfLocate._pathFromUrl('chrome-extension://oemmndcbldboiebfnladdacbdfmadadm/' + web), os.path.join(local, ACT))
check('PDF.js extension, a file on the computer', pdfLocate._pathFromUrl('chrome-extension://oemmndcbldboiebfnladdacbdfmadadm/file:///C:/Users/x/Documents/a%20b.pdf').replace('\\', '/'), 'C:/Users/x/Documents/a b.pdf')
check('the address of a browse mode document', pdfLocate.documentUrl(types.SimpleNamespace(documentConstantIdentifier='https://ekantipur.com/news')), 'https://ekantipur.com/news')

print('== a web page is known as one at once, and only once')
p = NR.GlobalPlugin()
while not p._ready:
    time.sleep(0.05)
F.state['app'] = 'chrome'
F.state['title'] = 'Online Khabar - Google Chrome'
F.state['fg'] += 1
looked = []
p._lookUpTitleLater = lambda *a: looked.append(a)
walks = []
_walk = pdfLocate._urlFromObject
pdfLocate._urlFromObject = lambda o: walks.append(o) or _walk(o)
page = types.SimpleNamespace(documentConstantIdentifier='https://www.onlinekhabar.com/2026/11/1', rootNVDAObject=types.SimpleNamespace(appModule=types.SimpleNamespace(appName='chrome')))
check('a news page is not a PDF', p._isPdfWindow(page), False)
check('no search for a PDF file under the page title', looked, [])
p._pdfMemo = None
p._isPdfWindow(page)
check('asked again a second later: answered from memory, no walk through the page', len(walks), 1)
pdfLocate._urlFromObject = _walk
pdfjs = types.SimpleNamespace(documentConstantIdentifier='chrome-extension://oemmndcbldboiebfnladdacbdfmadadm/' + web, rootNVDAObject=types.SimpleNamespace(appModule=types.SimpleNamespace(appName='chrome')))
F.state['title'] = ACT + ' - Google Chrome'
F.state['fg'] += 1
p._pdfMemo = None
check('the PDF.js viewer is a PDF window', p._isPdfWindow(pdfjs), True)

print('== the speech filter in a Unicode PDF')
st = p._docState()
st.recordWords('बालबालिका सम्बन्धी कानूनलाई संशोधन र एकीकरण गर्न बनेको ऐन प्रस्तावना बालबालिकाको अधिकारको सम्मान संरक्षण प्रवर्द्धन र परिपूर्ति गरी बालबालिकाको सर्वोत्तम')
p._clearContext()
said = lambda t: ''.join(x for x in p._filterSpeechSequence([t]) if isinstance(x, str))
check('":" alone is a colon, not स् (the Preeti key)', said(':'), ':')
check('"(" alone stays', said('('), '(')
check('"," alone stays', said(','), ',')

p._setContext('preeti')
check('in a Preeti PDF, ":" (Preeti M, already converted) is not converted again into स्', said(':'), ':')
check('a PDF\'s visarga alone (Preeti M drawn as ः) is read as a colon', said('\u0903'), ':')
check('...and after a word: संविधान मूल कानून ः reads संविधान मूल कानून :', said('संविधान मूल कानून \u0903'), 'संविधान मूल कानून :')
check('a glyph PDF.js could not name (\ufffd) is not spoken', said('स्थि\ufffdति'), 'स्थिति')
p._clearContext()

print('== patterns of PDF viewer text')
check('a heading drawn four times over itself (fake bold) is read once', devanagariRepair.collapseOverprint("P]gk|:tfjgk|:tfjgk|:tfjgk|:tfjgffff M"), "P]gk|:tfjgf M")
check('...a whole title four times', devanagariRepair.collapseOverprint("/fli6«o lgs'~h P]g, @)@(" * 4), "/fli6«o lgs'~h P]g, @)@(")
check('two copies are real Nepali and stay (ठाउँठाउँ, बेला बेला)', devanagariRepair.collapseOverprint('ठाउँठाउँ बेला बेला'), 'ठाउँठाउँ बेला बेला')
check('numbers and dot leaders stay (१,००,०००, @))), ........)', devanagariRepair.collapseOverprint('१,००,००० @))) ........ ------'), '१,००,००० @))) ........ ------')
check('a visarga before a dash is a colon in a PDF (यस ऐनमा ः–(क))', devanagariRepair.visargaAsColon('यस ऐनमा ः–(क)'), 'यस ऐनमा :–(क)')
check('a word the viewer cut after a halant is joined (सम् बन् धी)', devanagariRepair.repair('बालबाललका सम् बन् धी कानूनलाई', broken=True), 'बालबालिका सम्बन्धी कानूनलाई')
check('a real word ending in halant stays apart (अर्थात् यो ऐन)', devanagariRepair.repair('अर्थात् यो ऐन', broken=True), 'अर्थात् यो ऐन')
F.state['title'] = 'banyajantu sanrakshan ain pdf - Google Search - Google Chrome'
F.state['fg'] += 1
q = 'u+sanrakshan+ain+pdf&oq=banyajantu+&gs_lcrp=EgZjaHJvbWUqCAgAEEUYJxg7Mg'
check('a search address is never Preeti (it was read गंकबलच…)', said(q), q)

print('== background work gives way to NVDA')
NR._noteActivity()
y = NR._Yield()
t = time.monotonic(); y(); took = time.monotonic() - t
check('right after a key: the work rests until NVDA is done (%.2f s)' % took, 0.12 <= took <= 0.5)
NR._activity[0] = 0.0
t = time.monotonic(); y(); took = time.monotonic() - t
check('when nothing happens: no rest', took < 0.03)
stop = [False]
y2 = NR._Yield(stopped=lambda: stop[0])
NR._noteActivity()
stop[0] = True
try:
    y2(); check('switched off while resting: the work stops', False)
except NR._Stopped:
    check('switched off while resting: the work stops', True)
calls = []
devanagariRepair.learnDocumentSwaps('बालबाललका बालबाललकाको अलधकारको प्रचललि सम्बन्धी ' * 10, pause=lambda: calls.append(1))
check('learning a damaged document pauses often', len(calls) > 5)

print('== the log is written in the background, and stops with Nepali mode')
diag.write('test line')
diag.flush()
check('a line reaches diag.log', 'test line' in open(os.path.join(NR._cacheDir(), 'diag.log'), encoding='utf-8').read())
diag.write('another')
diag.stop()
check('switched off: no log thread left', [x.name for x in threading.enumerate() if x.name == 'NepaliReaderDiag'], [])

print('== a PDF that is being read does not hold NVDA up')
F.state['title'] = 'slow.pdf - Google Chrome'
F.state['fg'] += 1
gate = threading.Event()
_build = p._buildPdf
p._buildPdf = lambda st, *a: gate.wait(5)
info = types.SimpleNamespace(obj=types.SimpleNamespace(documentConstantIdentifier='https://x.gov.np/slow.pdf', rootNVDAObject=types.SimpleNamespace(appModule=types.SimpleNamespace(appName='chrome'))))
t = time.monotonic(); p._pdfIndex(info.obj); took = time.monotonic() - t
gate.set()
check('first line of a new PDF: NVDA waits at most a moment (%.2f s, was up to 4.5 s)' % took, took < 0.45)
p._buildPdf = _build

pdf = os.environ.get('CHROME_PDF_TEST')
if pdf and os.path.isfile(pdf):
    print('== the act read in Chrome through PDF.js, after the file was fetched')
    _read = pdfLocate.readPdf
    pdfLocate.readPdf = lambda loc, maxBytes=0: open(pdf, 'rb').read() if loc.startswith('http') else _read(loc)
    F.state['title'] = ACT + ' - Google Chrome'
    F.state['fg'] += 1
    os.remove(os.path.join(local, ACT))
    items = [s for s, _eol in json.load(open('tests/pdfjs_balbalika_p1.json', encoding='utf-8'))['items'] if s.strip()]

    class Item:
        def __init__(s, t):
            s.t = t
            s.obj = types.SimpleNamespace(documentConstantIdentifier='chrome-extension://oemmndcbldboiebfnladdacbdfmadadm/' + web, rootNVDAObject=types.SimpleNamespace(windowClassName='Chrome_RenderWidgetHostHWND', appModule=types.SimpleNamespace(appName='chrome')))
        text = property(lambda s: s.t)
        boundingRects = []
        def getTextWithFields(s, fc):
            return [F.FieldCommand('formatChange', F.FormatField({'font-name': 'sans-serif'})), s.t]
        def copy(s):
            return s
        def expand(s, unit):
            pass

    def spoken(t):
        seq = [x for x in next(SS.getTextInfoSpeech(Item(t))) if isinstance(x, str)]
        return ''.join(x for x in p._filterSpeechSequence(seq) if isinstance(x, str))

    spoken(items[0])
    t0 = time.time()
    while time.time() - t0 < 120:
        s = p._pdfs.get_(p._foregroundKey())
        if s and s.status in ('ready', 'none') and (s.full or s.status == 'none'):
            break
        time.sleep(0.2)
    check('the file was fetched from the web address PDF.js shows', (s.status, s.location), ('ready', web))
    got = {t: spoken(t) for t in items}
    for raw, want in [('गनन', 'गर्न'), ('प्रवर्द्नन', 'प्रवर्द्धन'), ('पररपूलिन', 'परिपूर्ति'), ('प्रस्िावना', 'प्रस्तावना'), ('अलधकारको', 'अधिकारको'),
                      ('संवि् २०७५ सालको ऐन नम्बर २३', 'संवत् २०७५ सालको ऐन नम्बर २३'), ('ो ऐन बनाएको छ', 'यो ऐन बनाएको छ'), ('प्रमाणीकरण लमलि', 'प्रमाणीकरण मिति'),
                      (':', ':'), ('”', '”'), ('“', '“'), ('२०७५', '२०७५'), ('(१)', '(१)')]:
        check('%s is read %s' % (raw, want), got.get(raw), want)
else:
    print('skip reading the act (set CHROME_PDF_TEST to बालबालिका-सम्बन्धी-ऐन-२०७५.pdf)')

p.terminate()
print('\n' + ('all passed' if not failures else '%d failed' % len(failures)))
sys.exit(1 if failures else 0)
