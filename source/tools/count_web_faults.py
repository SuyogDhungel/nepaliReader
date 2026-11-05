# Count invalid Devanagari sequences in a folder of web articles: python3 tools/count_web_faults.py <folder>
# python3 -I patterns.py <corpus dir> : invalid Devanagari sequences in real web text, by kind
import sys, os, re, collections, unicodedata
C = sys.argv[1]
CONS = '\u0915-\u0939\u0958-\u095f'; SIGNS = '\u093e-\u094c\u0962\u0963'; MODS = '\u0900-\u0903'
P = {
 'i before half letter (ि्X)': re.compile(f'\\S*\u093f\u094d\\S*'),
 'other sign + virama': re.compile(f'\\S*[{SIGNS.replace(chr(0x93f),"")}{MODS}]\u094d\\S*'),
 'two different vowel signs': re.compile(f'\\S*([{SIGNS}])(?!\\1)[{SIGNS}]\\S*'),
 'same vowel sign twice': re.compile(f'\\S*([{SIGNS}])\\1\\S*'),
 'nasal/visarga before vowel sign': re.compile(f'\\S*[{MODS}][{SIGNS}]\\S*'),
 'nasal twice': re.compile(f'\\S*([{MODS}])\\1\\S*'),
 'virama twice': re.compile('\\S*\u094d\u094d\\S*'),
 'sign at word start': re.compile(f'(?<!\\S)[{SIGNS}{MODS}\u094d]\\S*'),
 'independent vowel + sign': re.compile(f'\\S*[\u0905-\u0914][{SIGNS}]\\S*'),
 'Latin-1 symbol inside a word': re.compile(f'\\S*[\u0900-\u097f][\u00a1-\u00ff\u2018-\u201e\u2020-\u203a][\u0900-\u097f]\\S*'),
 'ZWJ/ZWNJ': re.compile('\\S*[\u200c\u200d]\\S*'),
 'lone visarga': re.compile('(?<!\\S)\u0903(?!\\S)'),
 'eyelash ra र्‍': re.compile('\\S*\u0930\u094d\u200d\\S*'),
}
files = [os.path.join(dp, f) for dp, _, fs in os.walk(C) for f in fs if f.endswith('.txt')]
cnt = {k: collections.Counter() for k in P}; total = 0
for f in files:
    t = unicodedata.normalize('NFC', open(f, encoding='utf-8', errors='replace').read()); total += len(t.split())
    for k, rx in P.items():
        for m in rx.finditer(t): cnt[k][m.group(0)] += 1
print(f'{len(files)} articles, {total} words')
for k, c in cnt.items():
    print(f'\n## {k}: {sum(c.values())} times, {len(c)} distinct')
    print('   ' + '  '.join(f'{w}×{n}' for w, n in c.most_common(14)))
