# Compare our Preeti-family converter with other open-source converters' test vectors.
#   git clone https://github.com/nepali-bhasa/ttf-to-unicode   (and Shuvayatra/preeti) into one folder, then
#   python3 tools/check_converter_vectors.py addon/globalPlugins/nepaliReader <that folder>
# Folder names expected: nepali-bhasa_ttf-to-unicode, Shuvayatra_preeti. Their data is not bundled (no licence).
# python3 -I vectors.py <our module dir> <conv-refs dir>  -- runs OUR converter on other projects' test vectors
import sys, json, unicodedata, collections
sys.path.insert(0, sys.argv[1]); C = sys.argv[2]
import legacyFonts, neLexicon
neLexicon.load()
def nfc(s): return unicodedata.normalize('NFC', s)
sets = []
def tsv(path, enc):
    out = []
    for line in open(path, encoding='utf-8-sig'):
        if '\t' in line:
            a, b = line.rstrip('\n').split('\t', 1); out.append((a, b))
    sets.append((path.split('/')[-1], enc, out))
def jpairs(path, enc):
    d = json.load(open(path, encoding='utf-8-sig')); sets.append((path.split('/')[-1], enc, list(zip(d[0::2], d[1::2]))))
V = C + '/nepali-bhasa_ttf-to-unicode/vectors/'
tsv(V + 'preeti.vector', 'preeti'); tsv(V + 'kantipur.vector', 'kantipur'); tsv(V + 'pcs_nepali.vector', 'pcs'); tsv(V + 'fontasy_himali_tt.vector', 'fontasy')
S = C + '/Shuvayatra_preeti/test/'
jpairs(S + 'preeti.vector.json', 'preeti'); jpairs(S + 'kantipur.vector.json', 'kantipur'); jpairs(S + 'pcs_nepali.vector.json', 'pcs')
def isword(t):
    ws = [w.strip('।,.;:!?()[]{}\'"‘’“”-–—/') for w in t.split()]
    ws = [w for w in ws if any('ऀ' <= ch <= 'ॿ' for ch in w)]
    return bool(ws) and all(neLexicon.isWord(w) for w in ws)
report = {}
for name, enc, pairs in sets:
    bad = []
    for src, want in pairs:
        got = nfc(legacyFonts.convert(src, enc) or '')
        if got != nfc(want):
            bad.append((src, want, got, isword(want), isword(got)))
    report[name] = bad
    tally = collections.Counter((w, g) for *_, w, g in bad)
    print(f'{name:<28} {enc:<9} {len(pairs):>5} pairs  differ {len(bad):>4}  '
          f'(theirs is a word & ours not: {tally[(True, False)]}, ours word & theirs not: {tally[(False, True)]}, both words: {tally[(True, True)]}, neither: {tally[(False, False)]})')
[print(f'  {n}: {s!r} theirs={w} ({wi}) ours={g} ({gi})') for n, b in report.items() for s, w, g, wi, gi in b]
