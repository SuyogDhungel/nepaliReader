# Word with Preeti: character / word navigation, selection speech and copy.
import sys, os, time, types
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
F.conf['nepaliReader'].update(enabled=True, pdfFile=True)
F.mod('globalVars', appArgs=types.SimpleNamespace(configPath='/root/work/nvdacfg'))
F.sys.modules['textInfos'].convertToCrlf = lambda t: t.replace('\n', '\r\n')
clip = []
class TI:
    def copyToClipboard(self, notify=False): clip.append('ORIG:' + self.text); return True
F.sys.modules['textInfos'].TextInfo = TI
F.sys.modules['api'].copyToClip = lambda t, notify=False: clip.append(t) or True
sys.path.insert(0, 'addon/globalPlugins')
import nepaliReader as NR, speech.speech as SS
p = NR.GlobalPlugin()
while not p._ready: time.sleep(0.05)
F.state['app'] = 'winword'; F.state['title'] = 'letter.docx - Word'
FC, FF = F.FieldCommand, F.FormatField
class LineInfo:
    def __init__(s, line, a=0, b=None, font='Preeti'):
        s.line = line; s.a = a; s.b = len(line) if b is None else b; s.font = font
        s.obj = types.SimpleNamespace(windowClassName='_WwG', appModule=types.SimpleNamespace(appName='winword'))
    def copy(s): return LineInfo(s.line, s.a, s.b, s.font)
    def expand(s, unit): s.a, s.b = 0, len(s.line)
    def setEndPoint(s, o, which):
        if which == 'endToStart': s.b = o.a
    @property
    def text(s): return s.line[s.a:s.b]
    def getTextWithFields(s, fc): return [FC('formatChange', FF({'font-name': s.font})), s.text]
    boundingRects = []
def say(info): return ''.join(x for x in next(SS.getTextInfoSpeech(info)) if isinstance(x, str))
for line in ['lzIff dGqfno', 'ljZjljBfno sf7df8f}+', 'cfof{gt k"0f{ ;dfrf/']:
    print('line :', say(LineInfo(line)))
    print('chars:', [say(LineInfo(line, i, i + 1)) for i in range(len(line))])
    ws = []; i = 0
    for w in line.split(' '):
        ws.append(say(LineInfo(line, i, i + len(w)))); i += len(w) + 1
    print('words:', ws)
clip.clear(); NR.textInfos.TextInfo.copyToClipboard(LineInfo('lzIff dGqfno'), True); print('copy :', clip)
print('english Calibri:', say(LineInfo('Office of the Prime Minister', font='Calibri')))
p.script_toggleNepaliMode(None); print('toggle ->', F.spoken[-1], '|', say(LineInfo('lzIff dGqfno')))
p.script_toggleNepaliMode(None); print('toggle ->', F.spoken[-1], '|', say(LineInfo('lzIff dGqfno')))
p.terminate()
