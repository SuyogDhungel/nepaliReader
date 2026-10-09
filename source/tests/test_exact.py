# Text rebuilt exactly from a PDF must never be changed again; Preeti digit symbols convert.
import sys, time
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
import nepaliReader as NR
from nepaliReader import devanagariRepair as DR, detector
p = NR.GlobalPlugin(); time.sleep(0.5)
bad = 0
def check(name, got, want):
    global bad
    ok = got == want; bad += not ok
    print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))

lines = ["नेपालको सुदुर पश्चिमाञ्चल विकास क्षेत्रको डोटी",
         "चन्द्र शम्शेरले वापत एक दास शिव भक्त भनिन्थ्यो ।"]
# repair damages these when it is allowed to guess (this is why exact text is protected)
check('repair would change an unprotected line', DR.repair(lines[0], broken=True) != lines[0], True)
for l in lines: DR.markExact(l)
for l in lines:
    check('repair leaves exact text: ' + l[:12], DR.repair(l, broken=True), l)
    check('cleanShuffled leaves exact text', DR.cleanShuffled(l), l)
# the speech filter (window titles, headers...) must not touch exact words either
F.state['app'] = 'brave'; F.state['title'] = 'x.pdf - Brave'
out = p._filterSpeechSequence([lines[0] + ' '])
check('speech filter keeps exact PDF text', ''.join(x for x in out if isinstance(x, str)).strip(), lines[0])
# Preeti digit symbols (shift + number row) are numbers, whatever the path
for t, want in [('!(*)', '१९८०'), ('@)&*', '२०७८'), ('!(*!', '१९८१')]:
    check('forceDecide ' + t, [f for tok, f in detector.forceDecide(t) if tok == t], [True])
line = 'lj= ;+= !(*) dª\\l;/ !$ ut]'
check('Preeti line with a year', ''.join(t for t, f in detector.decide(line, 'preeti') if f and t == '!(*)'), '!(*)')
check('English keeps its symbols', [f for t, f in detector.decide('Wow !! (nice) 50% #1', 'preeti') if f], [])
print('FAILED' if bad else 'ALL OK', bad)
sys.exit(1 if bad else 0)
