# All PDF benchmarks + correct-text checks, reading documents the way the add-on does
import sys, json, glob, collections, unicodedata, random, time
sys.path.insert(0,'/root/nepaliReader/addon/globalPlugins/nepaliReader')
import neLexicon; neLexicon.load()
import devanagariRepair as R, pypdfium2 as pdfium
R.loadConfusions()
P='।॥,.;:!?()[]{}\'"‘’“”-–—/•'
N=lambda s: unicodedata.normalize('NFC',s)
def words(t): return [w.strip(P) for w in t.split() if w.strip(P) and any('क'<=c<='ह' for c in w)]
def match(text, ref):
    c=collections.Counter(words(ref)); hit=0
    for w in words(text):
        if c[w]>0: c[w]-=1; hit+=1
    return hit, len(words(ref))
class Doc:  # same decision as the add-on
    def __init__(s): s.broken=False; s.g=0; s.n=0; s.done=False; s.k=0; s.w=0
    def read(s, line):
        if not s.broken and not s.done:
            k,w=R.wordStats(line); s.k+=k; s.w+=w
            if R.isBroken(line) or (s.w>=60 and s.k<0.5*s.w): s.broken=True
            else:
                u0,u1,n=R.repairGain(line); s.g+=u0-u1; s.n+=n
                if (s.n>=40 and s.g>=0.10*s.n) or (u0-u1>=2 and u0-u1>=0.3*n): s.broken=True
                elif s.n>=200: s.done=True
        return R.repair(line, broken=True if s.broken else None)
LEARN = True
def doc(lines):
    d=Doc()
    # like the add-on: once the document is found damaged, learn its pattern from the whole text
    for l in lines:
        d.read(l)
        if d.broken: break
    if d.broken and LEARN:
        R.setDocumentSwaps(R.learnDocumentSwaps('\n'.join(lines)), id(lines))
    else:
        R.setDocumentSwaps([], id(lines))
    d2=Doc(); out='\n'.join(d2.read(l) for l in lines)
    return out, d2.broken
if __name__=='__main__':
    B=json.load(open('/root/pdfs/bench.json'))
    t0=time.perf_counter(); nl=0
    for name,pages in B.items():
        H=T=Hr=0
        for pg in pages:
            ls=pg['pdfium'].splitlines(); nl+=len(ls)
            h,t=match(doc(ls)[0],pg['ocr']); H+=h; T+=t; Hr+=match(pg['pdfium'],pg['ocr'])[0]
        print(f'{name:30s} raw {Hr/T:5.1%} -> repaired {H/T:5.1%}   (vs OCR of the page)')
    print('ms per line', round((time.perf_counter()-t0)/nl*1000,2))
    truth=open('/root/pdfs/gen/truth.txt',encoding='utf8').read()
    for f in sorted(glob.glob('/root/pdfs/gen/*.pdf')):
        d=pdfium.PdfDocument(f); raw='\n'.join(d[i].get_textpage().get_text_range() for i in range(len(d)))
        out,br=doc(raw.splitlines()); h,t=match(out,truth); hr,_=match(raw,truth)
        print(f'{f.split("/")[-1]:30s} raw {hr/t:5.1%} -> repaired {h/t:5.1%}   (vs original text) damaged={br}')
    clean=[l.strip() for l in open('/root/nepaliReader/tests/sentences_ne.txt',encoding='utf8') if l.strip()]+truth.split('\n')
    ne=open('/root/ref/nedict/ne_words.txt',encoding='utf8').read().split('\n'); random.seed(1)
    rnd=[' '.join(random.sample(ne,10)) for _ in range(2000)]
    out,br=doc(clean+rnd)
    ch=sum(1 for a,b in zip(clean+rnd,out.split('\n')) if N(a)!=b)
    print('correct text read as a document: lines changed', ch,'of',len(clean+rnd),' damaged-detected:',br)
