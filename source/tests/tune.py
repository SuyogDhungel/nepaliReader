import sys, json, glob, collections, unicodedata, random
sys.path.insert(0,'/root/nepaliReader/addon/globalPlugins/nepaliReader')
import neLexicon; neLexicon.load()
import devanagariRepair as R, pypdfium2 as pdfium
P='।॥,.;:!?()[]{}\'"‘’“”-–—/•'
N=lambda s: unicodedata.normalize('NFC',s)
B=json.load(open('/root/pdfs/bench.json'))
def words(t): return [w.strip(P) for w in t.split() if w.strip(P) and any('क'<=c<='ह' for c in w)]
def match(text, ref):
    c=collections.Counter(words(ref)); hit=0
    for w in words(text):
        if c[w]>0: c[w]-=1; hit+=1
    return hit, len(words(ref))
gen={f:'\n'.join(pdfium.PdfDocument(f)[i].get_textpage().get_text_range() for i in range(len(pdfium.PdfDocument(f)))) for f in glob.glob('/root/pdfs/gen/*.pdf')}
truth=open('/root/pdfs/gen/truth.txt',encoding='utf8').read()
ne=open('/root/ref/nedict/ne_words.txt',encoding='utf8').read().split('\n')
random.seed(1)
clean=[l.strip() for l in open('tests/sentences_ne.txt',encoding='utf8') if l.strip()]+truth.split('\n')
def run(e,c):
    R.LENGTH_POWER=e; R.JOIN_COST=c; R._fixCache.clear()
    H=T=0
    for pages in B.values():
        for pg in pages:
            h,t=match('\n'.join(R.repair(l, broken=True) for l in pg['pdfium'].splitlines()), pg['ocr']); H+=h; T+=t
    G=[]
    for f,raw in gen.items():
        h,t=match('\n'.join(R.repair(l, broken=True) for l in raw.splitlines()), truth); G.append(h/t)
    changed=sum(1 for l in clean if R.repair(l, broken=True)!=N(l))
    return H/T, sum(G)/len(G), min(G), changed, len(clean)
for e in (1.0,1.2,1.4,1.6):
    for c in (0.5,1.0,2.0):
        r=run(e,c); print(f'power {e} cost {c}:  InDesign {r[0]:.1%}  generated avg {r[1]:.1%} (min {r[2]:.1%})  clean lines changed {r[3]}/{r[4]}')
