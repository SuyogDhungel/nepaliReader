import sys, os, re, collections, glob
sys.path.insert(0,'/root/work/pkg')
import pypdfium2 as pdfium
from nr import pdfText, glyphRefs, neLexicon, detector, devanagariRepair, legacyFonts
pdfText.INFER = not os.environ.get("NOINF2")
glyphRefs.load(path=os.environ.get('REFS','/root/corpus/heldout.dat'), cacheDir='/tmp/gr_cache_eval')
neLexicon.load(); detector.loadDictionary(); devanagariRepair.loadConfusions()
W=re.compile(r'[ऀ-ॿ]+')
truthU=open('/root/corpus/truth.txt',encoding='utf8').read()
truthP=open('/root/corpus/truth_preeti.txt',encoding='utf8').read()
def acc(out, truth):
    o=collections.Counter(W.findall(truth)); n=sum(o.values()); hit=0
    for w in W.findall(out):
        if o[w]>0: o[w]-=1; hit+=1
    return round(100*hit/max(1,n),1)
def viewer(path):
    doc=pdfium.PdfDocument(path); out=[]
    for i in range(len(doc)):
        out.append(doc[i].get_textpage().get_text_range())
    return '\n'.join(out)
def join(pieces):
    out=[];run=[]
    for p,ok in pieces:
        if ok:
            if run: out.append(devanagariRepair.repair(' '.join(run), broken=True)); run=[]
            out.append(p)
        else: run.append(p)
    if run: out.append(devanagariRepair.repair(' '.join(run), broken=True))
    return ' '.join(out)
rows=[]
for path in sorted(glob.glob('/root/corpus/pdf/*.pdf')):
    name=os.path.basename(path)[:-4]
    leg=any(k in name for k in ('Preeti','PCS','Kantipur','Untagged'))
    truth=truthP if leg else truthU
    try: raw=viewer(path)
    except Exception: continue
    if not raw.strip(): continue
    old=[]
    for l in raw.splitlines():
        t=devanagariRepair.repair(l)
        if leg:
            d=detector.decide(t,'preeti',context=False)
            t=detector.convertTokens(d, lambda s: legacyFonts.convert(s,'preeti') or s)
        old.append(t)
    idx=pdfText.DocIndex.build(open(path,"rb").read(), detector=detector, isWord=None if os.environ.get("NOINF") else neLexicon.isWord)
    new=[]
    for l in raw.splitlines():
        if not l.strip(): continue
        pc=idx.lookup(l)
        new.append(join(pc) if pc and any(ok for p,ok in pc) else old[raw.splitlines().index(l)])
    rows.append((name, acc(raw,truth), acc('\n'.join(old),truth), acc('\n'.join(new),truth)))
    print('%-34s viewer %5.1f  old %5.1f  NEW %5.1f'%rows[-1], flush=True)
import statistics
print('MEAN viewer %.1f old %.1f new %.1f'%tuple(statistics.mean(r[i] for r in rows) for i in (1,2,3)))
