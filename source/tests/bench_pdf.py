# Word-level comparison of PDF text (as Chrome/Edge extract it) with OCR of the same page.
import sys, json, re, collections, importlib.util, unicodedata
sys.path.insert(0,'/root/nepaliReader/addon/globalPlugins/nepaliReader')
import neLexicon; neLexicon.load()
import devanagariRepair as NEW
spec=importlib.util.spec_from_file_location('old','/tmp/devanagariRepair_v1.py'); OLD=importlib.util.module_from_spec(spec); spec.loader.exec_module(OLD)
B=json.load(open('/root/pdfs/bench.json'))
P='।॥,.;:!?()[]{}\'"‘’“”-–—/•'
def words(t): return [w.strip(P) for w in t.split() if re.search('[क-ह]',w) and w.strip(P)]
def score(text, ocr):
    ref=collections.Counter(words(unicodedata.normalize('NFC',ocr))); ws=words(text)
    hit=0
    for w in ws:
        if ref[w]>0: ref[w]-=1; hit+=1
    total=sum(collections.Counter(words(ocr)).values())
    return hit, len(ws), total
show='-v' in sys.argv
for label,fn in (('raw PDF text',lambda t:t),('repair v1.3',OLD.repair),('repair new',NEW.repair)):
    H=N=T=0
    for name,pages in B.items():
        for pg in pages:
            out='\n'.join(fn(l) for l in pg['pdfium'].splitlines())
            h,n,t=score(out,pg['ocr']); H+=h; N+=n; T+=t
    print(f'{label:14s} words matching OCR: {H}/{T} = {H/T:.1%}   (precision {H/max(N,1):.1%})')
if show:
    pg=B['sitrep.pdf'][0]
    for l in pg['pdfium'].splitlines()[:14]: print('RAW:',l); print('NEW:',NEW.repair(l))
def valid(text):
    ws=words(text); return sum(neLexicon.isWord(w) for w in ws), len(ws)
for label,fn in (('raw PDF text',lambda t:t),('repair new',NEW.repair),('OCR of page',None)):
    V=N=0
    for name,pages in B.items():
        for pg in pages:
            t=pg['ocr'] if fn is None else '\n'.join(fn(l) for l in pg['pdfium'].splitlines())
            v,n=valid(t); V+=v; N+=n
    print(f'{label:14s} words that are real Nepali words: {V}/{N} = {V/N:.1%}')
