# A PDF reading that spans several headings: every heading keeps its own (converted) text.
import sys, os, time, types
os.environ['HOME'] = '/root/work/home'
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
F.sys.modules['config'].conf.profiles = [{}]
sys.path.insert(0, 'addon/globalPlugins')
import nepaliReader as NR, speech.speech as SS
FC, FF = F.FieldCommand, F.FormatField
p = NR.GlobalPlugin()
while not p._ready: time.sleep(0.05)
F.state['app'] = 'brave'; F.state['title'] = 'tu_act.pdf - Brave'; F.state['fg'] = 77
class Info:
    def __init__(s, fields): s.fields = fields; s.obj = types.SimpleNamespace(rootNVDAObject=types.SimpleNamespace(appModule=types.SimpleNamespace(appName='brave')))
    def getTextWithFields(s, fc): return list(s.fields)
    @property
    def text(s): return ''.join(x for x in s.fields if isinstance(x, str))
    def copy(s): return s
    def expand(s, u): pass
    def setEndPoint(s, o, w): pass
    boundingRects = []
def H(t): return [FC('controlStart', FF({'role': 'heading'})), t, FC('controlEnd', None)]
fields = H("lqe'jg ljZjljBfno P]g, @)$(\r\n") + H('-ldlt @)&$ ;fn sflt{s d;fGt;Dd ePsf ;+zf]wg ;d]t ldnfOPsf]_\r\n') + H(' g]kfn ;/sf/\r\n')
next(SS.getTextInfoSpeech(Info(fields)))
for _ in range(200):
    st = p._pdfs.get_(p._foregroundKey())
    if st and st.status in ('ready', 'none'): break
    time.sleep(0.1)
print('status', st.status)
out = p._convertFields(Info(fields), None)
print([x if isinstance(x, str) else x.command for x in out])
