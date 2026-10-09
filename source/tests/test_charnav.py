# Character / word navigation must agree with line reading: English stays English, Preeti is converted.
import sys, time
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
import nepaliReader as NR, speech.speech as SS
FC, FF = F.FieldCommand, F.FormatField
p = NR.GlobalPlugin(); time.sleep(0.5)

class Info:
    """A caret on one line of a document; runs = [(font, text)]."""
    def __init__(s, runs, start, end=None, app='winword'):
        s.runs = runs; s.full = ''.join(t for _, t in runs); s.start = start; s.end = start + 1 if end is None else end
        s.obj = F.types.SimpleNamespace(windowClassName='_WwG', appModule=F.types.SimpleNamespace(appName=app), treeInterceptor=None)
    def copy(s): return Info(s.runs, s.start, s.end)
    def expand(s, unit):
        if unit == 'line': s.start, s.end = 0, len(s.full)
        elif unit == 'word':
            a = s.start
            while a > 0 and not s.full[a-1].isspace(): a -= 1
            b = s.start
            while b < len(s.full) and not s.full[b].isspace(): b += 1
            s.start, s.end = a, b
        else: s.end = s.start + 1
    def setEndPoint(s, other, which): s.end = other.start
    def move(s, unit, n): 
        s.start += n; s.end = s.start + 1; return n if 0 <= s.start < len(s.full) else 0
    @property
    def text(s): return s.full[s.start:s.end]
    def getTextWithFields(s, fc):
        out = []; pos = 0
        for font, t in s.runs:
            a, b = max(pos, s.start), min(pos + len(t), s.end)
            if a < b:
                if font: out.append(FC('formatChange', FF({'font-name': font})))
                out.append(s.full[a:b])
            pos += len(t)
        return out

def said(info, unit):
    seq = next(SS.getTextInfoSpeech(info, unit=unit))
    return ''.join(x for x in seq if isinstance(x, str))

def wordInfo(runs, i):
    x = Info(runs, i); x.expand('word'); return x

def chars(runs, unit='character'):
    full = ''.join(t for _, t in runs)
    return [said(Info(runs, i), unit) for i in range(len(full))]

bad = 0
def check(name, got, want):
    global bad
    ok = got == want
    bad += not ok
    print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))

# 1. Word, Preeti font for Nepali and Calibri for English
F.state['app'] = 'winword'
runs = [('Preeti', 'g]kfn '), ('Calibri', 'Report '), ('Preeti', ';/sf/')]
got = chars(runs)
check('font-tagged English by character', ''.join(got[6:12]), 'Report')
check('font-tagged Preeti by character', got[0] + got[1], 'न' + 'े')
# 2. No font information (notepad / browser / pdf viewer): mixed line
p._clearContext()
runs = [(None, 'g]kfn ;/sf/ Roshan Gautam office of the NVDA team')]
line = runs[0][1]
got = chars(runs)
i = line.index('Roshan'); check('plain English name by character', ''.join(got[i:i+13]), 'Roshan Gautam')
i = line.index('NVDA'); check('plain English acronym by character', ''.join(got[i:i+4]), 'NVDA')
i = line.index('office'); check('plain English word by character', ''.join(got[i:i+6]), 'office')
check('plain Preeti still converted', got[0] + got[1], 'न' + 'े')
# 3. English symbols / digits next to English
runs = [(None, 'Total (2024) 50% done [ok] M ')]
got = chars(runs)
check('English symbols untouched', ''.join(got[:28]), 'Total (2024) 50% done [ok] M')
# 4. Pure Preeti line keeps converting every character
p._clearContext()
runs = [('Preeti', 'g]kfn ;/sf/')]
got = chars(runs)
check('Preeti-only line converts by character', got[0], 'न')
# 5. words
runs = [('Preeti', 'g]kfn '), ('Calibri', 'Report '), ('Preeti', ';/sf/')]
check('word read: English', said(wordInfo(runs, 7), 'word').strip(), 'Report')
check('word read: Preeti', said(wordInfo(runs, 1), 'word').strip(), 'नेपाल')
print('FAILED' if bad else 'ALL OK', bad)
sys.exit(1 if bad else 0)
