# Live test with a fake NVDA: a PDF open in a viewer; speech, character / word navigation, copy.
import sys, os, time, json, types
os.environ['HOME'] = '/root/work/home'
os.environ['NEPALIREADER_FONTDIRS'] = '/root/work:/root/work/ref'
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
F.conf['nepaliReader'].update(enabled=True, pdfFile=True)
clip = []
gv = F.mod('globalVars', appArgs=types.SimpleNamespace(configPath='/root/work/nvdacfg'))
F.sys.modules['textInfos'].convertToCrlf = lambda t: t.replace('\n', '\r\n')
class TI:
    def copyToClipboard(self, notify=False): clip.append("ORIG:"+self.text); return True
F.sys.modules['textInfos'].TextInfo = TI

F.sys.modules['api'].copyToClip = lambda t, notify=False: clip.append(t) or True
sys.path.insert(0, 'addon/globalPlugins')
import nepaliReader as NR, speech.speech as SS
p = NR.GlobalPlugin()
for _ in range(100):
    if p._ready: break
    time.sleep(0.1)
F.state['app'] = 'chrome'

class LineInfo:
    def __init__(s, line, a=0, b=None):
        s.line = line; s.a = a; s.b = len(line) if b is None else b
        s.obj = types.SimpleNamespace(rootNVDAObject=types.SimpleNamespace(windowClassName='Chrome_RenderWidgetHostHWND', appModule=types.SimpleNamespace(appName=F.state['app'])))  # browse mode: a tree interceptor
    def copy(s): return LineInfo(s.line, s.a, s.b)
    def expand(s, unit): s.a, s.b = 0, len(s.line)
    def setEndPoint(s, o, which):
        if which == 'endToStart': s.b = o.a
    @property
    def text(s): return s.line[s.a:s.b]
    def getTextWithFields(s, fc): return [s.text]
    boundingRects = []
def say(info):
    return ''.join(x for x in next(SS.getTextInfoSpeech(info)) if isinstance(x, str))

bench = json.load(open('/root/pdfs/bench.json'))
for name in ('bulletin.pdf', 'ew4all.pdf'):
    F.state['title'] = name + ' - Google Chrome'; F.state['fg'] += 1
    lines = [l for pg in bench[name] for l in pg['pdfium'].splitlines() if l.strip()]
    say(LineInfo(lines[0]))  # starts reading the file in the background
    for _ in range(300):
        st = p._pdfs.get_(p._foregroundKey())
        if st and st.status in ('ready', 'none'): break
        time.sleep(0.1)
    print('==', name, 'status', st.status, st.location)
    for l in lines[8:12]:
        print('  viewer:', l[:80]); print('  spoken:', say(LineInfo(l))[:80])
    l = lines[10]
    print('  characters:', [say(LineInfo(l, i, i + 1)) for i in range(0, 14)])
    words = []; i = 0
    while i < len(l):
        j = l.find(' ', i); j = len(l) if j < 0 else j
        if j > i: words.append(say(LineInfo(l, i, j)))
        i = j + 1
    print('  words:', words[:10])
    clip.clear(); NR.textInfos.TextInfo.copyToClipboard(LineInfo(l), True); print('  copied:', clip[-1][:80] if clip else None)
    t = time.perf_counter()
    for l2 in lines[:200]: say(LineInfo(l2))
    print('  ms per line', round((time.perf_counter() - t) / 200 * 1000, 2))
p.terminate()
