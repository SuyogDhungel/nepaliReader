# What the typed-Unicode repair changes in real web text, and which faults web text has.
#   python3 tools/check_web_corpus.py addon/globalPlugins/nepaliReader <folder of .txt articles> [N]
# Used with github.com/ashokbasnet/nepali-news-dataset (72,000 articles from five news sites, research use).
# python3 -I webcheck.py <our module dir> <corpus dir> [N]: what the Unicode repair changes in real web news text
import sys, os, random, collections, difflib, time, unicodedata
sys.path.insert(0, sys.argv[1]); C = sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
import neLexicon, devanagariRepair as dr, detector
neLexicon.load(); dr.loadConfusions(); detector.loadDictionary()
files = []
for cat in sorted(os.listdir(C)):
    p = os.path.join(C, cat)
    if os.path.isdir(p) and not cat.startswith('.'):
        files += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.endswith('.txt')]
random.seed(11); files = random.sample(files, min(N, len(files)))
changes = collections.Counter(); lines = changedLines = brokenLines = 0; examples = {}
t0 = time.time()
for f in files:
    for line in open(f, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line or not dr.hasDevanagari(line): continue
        lines += 1
        nfc = unicodedata.normalize('NFC', line)
        out = dr.repairTyped(line)
        if dr.isBroken(line): brokenLines += 1
        if out != nfc:
            changedLines += 1
            a, b = nfc.split(), out.split()
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
                if tag != 'equal':
                    k = (' '.join(a[i1:i2]), ' '.join(b[j1:j2]))
                    changes[k] += 1; examples.setdefault(k, os.path.basename(f))
print(f'{len(files)} articles, {lines} lines, {brokenLines} lines judged broken, {changedLines} lines changed ({changedLines/max(lines,1):.2%}), {time.time()-t0:.0f} s')
for (a, b), n in changes.most_common(25):
    print(f'{n:4}  {a!r} -> {b!r}')
rare = [k for k, n in changes.items() if n == 1]
random.seed(3)
print('--- random rare changes')
for a, b in random.sample(rare, min(70, len(rare))): print(f'     {a!r} -> {b!r}')
