# Usage: score.py <pairs.tsv> <fixer name>   fixer: 'glyph' (new module alone)
import sys, difflib, time, re, unicodedata
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon', 'globalPlugins', 'nepaliReader'))
import neLexicon; neLexicon.load()
import glyphOrder as G, legacyFonts as L, detector as D
G.setDictionary(neLexicon.isWord); D.loadDictionary(); G.setEnglishCheck(D.isEnglishWord)

def tok(s):
    return re.sub(r'([।,?!])', r' \1 ', s).split()

def acc(pairs):
    n = same = 0
    for ref, hyp in pairs:
        ra = tok(ref); rb = tok(hyp)
        sm = difflib.SequenceMatcher(a=ra, b=rb, autojunk=False)
        same += sum(m.size for m in sm.get_matching_blocks()); n += len(ra)
    return 100.0 * same / n

def nospace(s):
    return re.sub(r'\s+', '', s)

pairs = [l.rstrip('\n').split('\t') for l in open(sys.argv[1], encoding='utf-8') if '\t' in l]
pat = G.Pattern()
t0 = time.time()
fixed = [(a, G.fixLine(b, pat, convertPreeti=lambda t: L.convert(t, 'preeti'))) for a, b in pairs]
dt = time.time() - t0
print('damaged : %.1f%% words right' % acc(pairs))
print('fixed   : %.1f%% words right   (%.1f ms per line)' % (acc(fixed), 1000 * dt / len(pairs)))
print('letters right ignoring spaces: %.1f%%' % (100.0 * sum(nospace(a) == nospace(b) for a, b in fixed) / len(fixed)), 'of lines fully right')
# do no harm: the clean text through the same repair
p2 = G.Pattern()
clean = [(a, G.fixLine(a, p2, convertPreeti=lambda t: L.convert(t, 'preeti'))) for a, _b in pairs]
changedLines = [(a, b) for a, b in clean if a != b]
print('clean text changed: %d of %d lines (%.2f%% words right)' % (len(changedLines), len(clean), acc(clean)))
for a, b in changedLines[:8]:
    print('   ', a[:110]); print(' -> ', b[:110])
bad = [(a, b, f) for (a, b), (_x, f) in zip(pairs, fixed) if a != f]
print('\nexamples still wrong:')
import random
random.Random(3).shuffle(bad)
for a, b, f in bad[:10]:
    ra, rf = a.split(), f.split()
    sm = difflib.SequenceMatcher(a=ra, b=rf, autojunk=False)
    diffs = [(' '.join(ra[i1:i2]), ' '.join(rf[j1:j2])) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal']
    print('   ', diffs[:4])
