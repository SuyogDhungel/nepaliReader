# Every Nepali letter, sign, digit and conjunct, written as Preeti keystrokes and converted back.
# References: npttf2utf (Python) and the "preeti" npm package (FOSS Nepal regular expressions).
import sys, json, subprocess, unicodedata, collections, os, re
sys.path.insert(0,'addon/globalPlugins/nepaliReader')
import legacyFonts as LF
from npttf2utf.base.preetimapper import convert as toPreeti
from npttf2utf.base.fontmapper import FontMapper
import npttf2utf
FM=FontMapper(os.path.join(os.path.dirname(npttf2utf.__file__),'map.json'))
N=lambda s: unicodedata.normalize('NFC',s)
CONS=list('कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह')+['क्ष','त्र','ज्ञ']
VOW=['अ','आ','इ','ई','उ','ऊ','ऋ','ए','ऐ','ओ','औ','अं','अः','अँ']
MAT=['ा','ि','ी','ु','ू','ृ','े','ै','ो','ौ']
MOD=['ँ','ं','ः']
DIG=list('०१२३४५६७८९')
items=collections.OrderedDict()
def add(cat,u): items.setdefault(cat,[]).append(u)
for v in VOW: add('independent vowels',v)
for d in DIG: add('digits',d)
add('digits','२०८३'); add('digits','१,२५०.५०')
for c in CONS:
    add('consonants',c)
    for m in MAT: add('consonant + vowel sign',c+m)
    for md in MOD: add('consonant + ँ ं ः',c+md)
    for m in MAT:
        for md in ('ँ','ं'): add('vowel sign + ँ/ं',c+m+md)
    add('half letters (consonant + ्)',c+'्')
    if c!='र':
        add('reph (र् + consonant)','र्'+c)
        add('reph + vowel sign','र्'+c+'ि'); add('reph + vowel sign','र्'+c+'ा'); add('reph + vowel sign','र्'+c+'े')
        add('र-subscript (consonant + ्र)',c+'्र')
        add('र-subscript + vowel sign',c+'्रि'); add('र-subscript + vowel sign',c+'्रा')
# conjuncts actually used in Nepali (from the dictionary)
lex=open('/root/ref/nedict/ne_words.txt',encoding='utf8').read().split('\n')
cl=collections.Counter()
for w in lex[::5]:
    for m in re.finditer('[क-ह](?:्[क-ह])+',w): cl[m.group(0)]+=1
for c,n in cl.most_common(400):
    add('conjuncts (most used 400)',c)
    add('conjuncts + ि',c+'ि'); add('conjuncts + ा',c+'ा')
add('punctuation','।'); add('punctuation','?'); add('punctuation','(क)'); add('punctuation','क, ख')
# second reference: preeti.js
allp={cat:[toPreeti(u) for u in us] for cat,us in items.items()}
js=subprocess.run(['node','-e','const p=require("/root/ref/preeti/preeti.js");const a=JSON.parse(require("fs").readFileSync(0));console.log(JSON.stringify(a.map(x=>p(x))))'],
    input=json.dumps([p for ps in allp.values() for p in ps]),capture_output=True,text=True)
jsout=json.loads(js.stdout); k=0
tot=collections.Counter(); bad=collections.defaultdict(list)
for cat,us in items.items():
    for u,p in zip(us,allp[cat]):
        ref1=N(FM.map_to_unicode(p,'Preeti')); ref2=N(jsout[k]); k+=1
        ours=N(LF.preetiFamilyToUnicode(p))
        tot[cat,'n']+=1
        if ours==N(u): tot[cat,'ok']+=1
        else: bad[cat].append((u,p,ours,ref1,ref2))
        if ref1==N(u): tot[cat,'r1']+=1
        if ref2==N(u): tot[cat,'r2']+=1
print(f'{"group":34s} {"ours":>9s} {"npttf2utf":>10s} {"preeti.js":>10s}')
for cat in items:
    n=tot[cat,'n']; print(f'{cat:34s} {tot[cat,"ok"]:4d}/{n:<4d} {tot[cat,"r1"]:5d}/{n:<4d} {tot[cat,"r2"]:5d}/{n:<4d}')
json.dump({c:v for c,v in bad.items()},open('tests/letters/failures.json','w'),ensure_ascii=False,indent=1)
for c,v in bad.items():
    print('--',c); [print('   want',x[0],'| keys',repr(x[1]),'| ours',x[2],'| npttf2utf',x[3],'| preeti.js',x[4]) for x in v[:6]]
