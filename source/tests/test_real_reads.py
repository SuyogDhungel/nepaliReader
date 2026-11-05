# What NVDA really got from Chrome's "PDF Viewer" extension (PDF.js), line by line, for two acts
# (from a user's diag.log), read again with the PDF file known: every line must read as printed.
# Run from the source folder:  NEPALI_TEST_PDFS=<folder with the two PDFs> python tests/test_real_reads.py
#   बालबालिका-सम्बन्धी-ऐन-२०७५.pdf  https://supremecourt.gov.np/web/assets/downloads/
#   NPWC Act 2029.pdf               https://snp.gov.np/uploads/legislation/
import json, os, sys, tempfile, time, types, urllib.parse
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
cfg = tempfile.mkdtemp(prefix='nr_realreads_')
F.mod('globalVars', appArgs=types.SimpleNamespace(configPath=cfg))
os.environ['HOME'] = os.path.join(cfg, 'home')
import nepaliReader as NR, speech.speech as SS
from nepaliReader import pdfLocate

folder = os.environ.get('NEPALI_TEST_PDFS', '')
data = json.load(open('tests/real_reads_chrome_pdfjs.json', encoding='utf-8'))['pdfs']
SITES = {'बालबालिका-सम्बन्धी-ऐन-२०७५.pdf': 'https://supremecourt.gov.np/web/assets/downloads/',
         'NPWC Act 2029.pdf': 'https://snp.gov.np/uploads/legislation/'}
missing = [n for n in data if not os.path.isfile(os.path.join(folder, n))]
if missing:
    print('skip: set NEPALI_TEST_PDFS to a folder with ' + ', '.join(missing))
    sys.exit(0)
pdfLocate.readPdf = lambda loc, maxBytes=0: open(os.path.join(folder, urllib.parse.unquote(loc.rsplit('/', 1)[-1])), 'rb').read()
p = NR.GlobalPlugin()
while not p._ready:
    time.sleep(0.05)
F.state['app'] = 'chrome'


class Line:
    def __init__(s, t, url):
        s.t = t
        s.obj = types.SimpleNamespace(documentConstantIdentifier=url, rootNVDAObject=types.SimpleNamespace(windowClassName='Chrome_RenderWidgetHostHWND', appModule=types.SimpleNamespace(appName='chrome')))
    text = property(lambda s: s.t)
    boundingRects = []
    def getTextWithFields(s, fc):
        return [F.FieldCommand('formatChange', F.FormatField({'font-name': 'sans-serif'})), s.t]
    def copy(s):
        return s
    def expand(s, unit):
        pass


def spoken(t, url):
    seq = [x for x in next(SS.getTextInfoSpeech(Line(t, url))) if isinstance(x, str)]
    return ''.join(x for x in p._filterSpeechSequence(seq) if isinstance(x, str))


failures = 0
total = 0
for name, lines in data.items():
    F.state['title'] = name + ' - Google Chrome'
    F.state['fg'] += 1
    url = 'chrome-extension://oemmndcbldboiebfnladdacbdfmadadm/' + SITES[name] + urllib.parse.quote(name)
    spoken('x', url)
    t0 = time.time()
    while time.time() - t0 < 120:
        st = p._pdfs.get_(p._foregroundKey())
        if st and st.status in ('ready', 'none') and (st.full or st.status == 'none'):
            break
        time.sleep(0.2)
    print('== %s (%s)' % (name, st.status))
    for got, want in lines:
        total += 1
        said = spoken(got, url)
        if said.strip() != want.strip():
            failures += 1
            print('FAIL %r\n     reads %r\n     want  %r' % (got, said, want))
print('%d of %d lines read as printed' % (total - failures, total))
p.terminate()
print('all passed' if not failures else '%d failed' % failures)
sys.exit(1 if failures else 0)
