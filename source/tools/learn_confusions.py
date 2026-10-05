# Learns which letters a damaged PDF text layer swaps, by aligning the PDF's text with OCR of
# the same pages. Output: confusions.json (pairs "as extracted" -> "as on the page"), used at
# run time only to propose corrections that must also be dictionary words.
import sys, json, difflib, collections, unicodedata
sys.path.insert(0,'addon/globalPlugins/nepaliReader')
import neLexicon; neLexicon.load()
import devanagariRepair as R
P='।॥,.;:!?()[]{}\'"‘’“”-–—/•'
N=lambda s: unicodedata.normalize('NFC',s)
docs=json.load(open('/root/pdfs/bench.json'))
holdout=set(sys.argv[1:])   # documents left out of learning (for testing)
pairs=collections.Counter()
for name,pages in docs.items():
    if name in holdout: continue
    for pg in pages:
        ext=[w.strip(P) for l in pg['pdfium'].splitlines() for w in R.repair(l,broken=True).split()]
        ocr=[w.strip(P) for w in N(pg['ocr']).split()]
        ext=[w for w in ext if w]; ocr=[w for w in ocr if w]
        sm=difflib.SequenceMatcher(None,ext,ocr,autojunk=False)
        for op,i1,i2,j1,j2 in sm.get_opcodes():
            if op!='replace' or i2-i1!=j2-j1: continue
            for a,b in zip(ext[i1:i2],ocr[j1:j2]):
                if not neLexicon.isWord(b) or neLexicon.isWord(a): continue
                a,b=R.toVisual(a),R.toVisual(b)
                cs=difflib.SequenceMatcher(None,a,b,autojunk=False)
                if cs.ratio()<0.6: continue
                for o,x1,x2,y1,y2 in cs.get_opcodes():
                    if o=='equal': continue
                    src,dst=a[x1:x2],b[y1:y2]
                    if len(src)<=3 and len(dst)<=3: pairs[(src.replace(R.REPH_MARK,'R'),dst.replace(R.REPH_MARK,'R'))]+=1
keep={f'{a}\t{b}':n for (a,b),n in pairs.items() if n>=2 and a}
json.dump(keep,open('addon/globalPlugins/nepaliReader/confusions.json','w'),ensure_ascii=False,indent=0)
print(len(keep),'confusions; top:',sorted(keep.items(),key=lambda x:-x[1])[:30])
