# Reads the material in bench.json (correct news lines, lines with moved signs, Preeti words in
# Unicode lines, Preeti lines, real PDF lines) with one version of the add-on through the test copy
# of NVDA, and writes how many words each set reads right.
# Usage: bench.py <version folder> <out.json>
#   <version folder> holds that version's addon/ and tests/fakenvda/ (for this version: source/)
import json, os, sys, tempfile, time, types, difflib, re
BENCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bench.json')
src = sys.argv[1]; outPath = os.path.abspath(sys.argv[2])
os.chdir(src)
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
cfg = tempfile.mkdtemp(prefix='nr_bench_')
F.mod('globalVars', appArgs=types.SimpleNamespace(configPath=cfg))
os.environ['HOME'] = os.path.join(cfg, 'home')
import nepaliReader as NR, speech.speech as SS
try:
    from nepaliReader import pdfLocate
    pdfLocate.readPdf = lambda *a, **k: None
except Exception:
    pass
p = NR.GlobalPlugin()
t0 = time.time()
while not getattr(p, '_ready', True) and time.time() - t0 < 90:
    time.sleep(0.05)
B = json.load(open(BENCH, encoding='utf-8'))

class Line:
    def __init__(s, t, font, url=None, app='chrome'):
        s.t, s.font = t, font
        s.obj = types.SimpleNamespace(documentConstantIdentifier=url, rootNVDAObject=types.SimpleNamespace(windowClassName='Chrome_RenderWidgetHostHWND', appModule=types.SimpleNamespace(appName=app)))
    text = property(lambda s: s.t)
    boundingRects = []
    def getTextWithFields(s, fc):
        out = []
        if s.font: out.append(F.FieldCommand('formatChange', F.FormatField({'font-name': s.font})))
        out.append(s.t)
        return out
    def copy(s): return s
    def expand(s, unit): pass

def spoken(t, font, url, app):
    seq = [x for x in next(SS.getTextInfoSpeech(Line(t, font, url, app))) if isinstance(x, str)]
    f = getattr(p, '_filterSpeechSequence', None)
    if f:
        try: seq = f(seq)
        except Exception: pass
    return ''.join(x for x in seq if isinstance(x, str))

CTX = {
    'pdf': ('chrome', 'notice.pdf - Google Chrome', 'sans-serif', 'chrome-extension://oemmndcbldboiebfnladdacbdfmadadm/https://example.org/notice.pdf'),
    'web': ('chrome', 'News - Google Chrome', 'sans-serif', 'https://example.org/news/1'),
    'word': ('winword', 'notice.docx - Word', 'Kalimati', None),
    'wordPreeti': ('winword', 'notice.docx - Word', 'Preeti', None),
}
PLAN = [('clean', 'pdf'), ('clean', 'web'), ('clean', 'word'), ('damaged', 'pdf'), ('damaged', 'web'), ('mixed', 'pdf'), ('preeti', 'wordPreeti'), ('preeti', 'pdf'), ('real', 'pdf')]

def tok(s):
    return re.sub(r'([।,?!])', r' \1 ', s).split()

res = {}
for setName, ctx in PLAN:
    app, title, font, url = CTX[ctx]
    F.state['app'] = app; F.state['title'] = title; F.state['fg'] += 1
    n = same = changed = 0; errors = 0; t1 = time.time(); outs = []
    for ref, inp in B[setName]:
        try:
            out = spoken(inp, font, url, app)
        except Exception as e:
            out = inp; errors += 1
        out = out.strip(); outs.append(out)
        ra, rb = tok(ref), tok(out)
        sm = difflib.SequenceMatcher(a=ra, b=rb, autojunk=False)
        same += sum(m.size for m in sm.get_matching_blocks()); n += len(ra)
        changed += out != inp.strip()
    res[setName + '/' + ctx] = {'acc': round(100.0 * same / max(1, n), 1), 'changed': changed, 'lines': len(B[setName]), 'errors': errors, 'msPerLine': round(1000 * (time.time() - t1) / max(1, len(B[setName])), 1), 'outs': outs}
    print(setName, ctx, res[setName + '/' + ctx]['acc'], flush=True)
json.dump(res, open(outPath, 'w', encoding='utf-8'), ensure_ascii=False)
