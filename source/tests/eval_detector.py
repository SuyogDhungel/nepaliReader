import sys, json, random, time
sys.path.insert(0,'addon/globalPlugins/nepaliReader')
import detector as D, legacyFonts as LF
print('dict words', D.loadDictionary())
from npttf2utf.base.preetimapper import convert as toPreeti
H=json.load(open('tests/heldout.json'))
random.seed(3)
def lineRate(lines, enc, expectLegacy):
    wrong=[l for l in lines if (D.looksLegacy(l,enc)!=expectLegacy)]
    return len(wrong), len(lines), wrong[:8]
en_sent = [l.strip() for l in open('tests/english.txt') if l.strip()]
ne_sent = [toPreeti(l.strip()) for l in open('tests/sentences_ne.txt',encoding='utf8') if l.strip()]
# synthetic preeti lines from held-out words
pre_lines=[' '.join(random.sample(H['hiHeldPreeti'],random.randint(2,9))) for _ in range(2000)]
kru_lines=[' '.join(random.sample(H['hiHeldKruti'],random.randint(2,9))) for _ in range(2000)]
en_words=H['enHeld']
en_lines=[' '.join(random.sample(en_words,random.randint(2,9))) for _ in range(2000)]
print('EN sentences  -> preeti FP', lineRate(en_sent,'preeti',False))
print('EN sentences  -> kruti  FP', lineRate(en_sent,'krutidev',False))
print('EN rare-word lines -> preeti FP', lineRate(en_lines,'preeti',False)[:2])
print('EN rare-word lines -> kruti FP', lineRate(en_lines,'krutidev',False)[:2])
print('NE sentences recall miss', lineRate(ne_sent,'preeti',True))
print('Preeti lines miss', lineRate(pre_lines,'preeti',True)[:2])
print('Kruti lines miss', lineRate(kru_lines,'krutidev',True)[:2])
sw=[w for w in H['hiHeldPreeti'] if len(w)>=3][:3000]
print('single preeti word recall', sum(D.looksLegacy(w) for w in sw)/len(sw))
se=[w for w in en_words if len(w)>=3][:5000]
print('single EN rare word FP', sum(D.looksLegacy(w) for w in se)/len(se), [w for w in se if D.looksLegacy(w)][:20])
t=time.perf_counter(); 
for l in en_sent*50+ne_sent*50: D.convertMixed(l, LF.preetiFamilyToUnicode)
n=len(en_sent*50+ne_sent*50); print('ms per line', (time.perf_counter()-t)*1000/n)
