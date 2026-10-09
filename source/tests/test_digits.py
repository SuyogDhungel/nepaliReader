# Digits, brackets and signs are read as shown; a digit becomes a letter only where the dictionary proves it.
import sys, time
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
import nepaliReader as NR, speech.speech as SS
from nepaliReader import devanagariRepair as DR, neLexicon, legacyFonts
p = NR.GlobalPlugin()
for _ in range(100):
    if neLexicon.isLoaded(): break
    time.sleep(0.1)
bad = 0
def check(name, got, want):
    global bad
    ok = got == want; bad += not ok
    print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))

# real digits stay digits
for t in ['ना२ख ९७५७', 'वि.सं. १९८० मा', 'धारा ९ र (९) र (क)', 'नं.पा.-१२', 'राम्रो! कस्तो% स्रोत*', 'गोरखा-९']:
    check('repair keeps ' + t, DR.repair(t, broken=True), t)
    check('isBroken ' + t, DR.isBroken(t), False)
# a number plate is not a damaged word
check('plan: plate', DR.gluedDigitPlan('ना२ख'), None)
# a Preeti digit key inside a word is a letter only if that makes the word
check('plan: बा६ -> बाट', ''.join(DR.gluedDigitPlan('बा६') or []), 'बाट')
check('plan: यु४ -> युद्ध', ''.join(DR.gluedDigitPlan('यु४') or []), 'युद्ध')
check('repair: बा६ रेक८', DR.repair('बा६ रेक८ १९८०', broken=True).split()[0], 'बाट')

# the Preeti keys ( ) between two Preeti words are the digit keys
check('lone ( is ९', legacyFonts.convert('vf; ( hgf', 'preeti'), 'खास ९ जना')
check('( ) of a clause stay brackets', legacyFonts.convert('(s) v', 'preeti'), '(क) ख')

# character and word reading of numbers
F.state['app'] = 'winword'
class Info:
    def __init__(s, text, a, b=None):
        s.full = text; s.start = a; s.end = a + 1 if b is None else b
        s.obj = F.types.SimpleNamespace(windowClassName='_WwG', appModule=F.types.SimpleNamespace(appName='winword'), treeInterceptor=None)
    def copy(s): return Info(s.full, s.start, s.end)
    def expand(s, unit):
        if unit == 'line': s.start, s.end = 0, len(s.full)
        elif unit == 'word':
            a = s.start
            while a > 0 and not s.full[a-1].isspace(): a -= 1
            b = s.start
            while b < len(s.full) and not s.full[b].isspace(): b += 1
            s.start, s.end = a, b
        else: s.end = s.start + 1
    def setEndPoint(s, o, w): s.end = o.start
    def move(s, unit, n): s.start += n; s.end = s.start + 1; return n if 0 <= s.start < len(s.full) else 0
    @property
    def text(s): return s.full[s.start:s.end]
    def getTextWithFields(s, fc): return [s.text]
def said(i, unit): return ''.join(x for x in next(SS.getTextInfoSpeech(i, unit=unit)) if isinstance(x, str))
def chars(t): return [said(Info(t, i), 'character') for i in range(len(t))]
def word(t, i):
    x = Info(t, i); x.expand('word'); return said(x, 'word').strip()
line = 'वि.सं. १९८० मा धारा ९ र (९) र ५०% छ'
check('Unicode digits by character', ''.join(chars(line)), line)
line = 'g]kfnsf] ;+ljwfg @)&@ ;fndf hf/L eof]'
check('Preeti year by word', word(line, line.index('@')), '२०७२')
check('Preeti year by character', ''.join(chars(line)[line.index('@'):line.index('@') + 4]), '२०७२')
line = 'Section 9 (a) of the Act, call (01) 4411234'
check('English numbers by character', ''.join(chars(line)), line)
print('FAILED' if bad else 'ALL OK', bad)
sys.exit(1 if bad else 0)

# Preeti overlay key m after प / भ, stray reph, extra halant (rebuilt PDF words)
for w, want in [('आप्mना', 'आफ्ना'), ('बुभ्mदा', 'बुझ्दा'), ('समेतलार्ई', 'समेतलाई'), ('कार्य्विधिको', 'कार्यविधिको'), ('mobile', None), ('हुनेछ।', None)]:
    got = DR.finalClean(w, neLexicon.isWord)
    check('finalClean ' + w, got, want)
print('ALL OK', bad)
