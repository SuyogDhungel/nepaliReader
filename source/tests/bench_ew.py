import sys, json, time, pypdfium2 as pdfium
sys.path.insert(0,'/root/nepaliReader/tests'); sys.argv=['x']
import bench_all as BA
R=BA.R
pdf=pdfium.PdfDocument('/root/pdfs/ew4all.pdf')
full='\n'.join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
t=time.perf_counter(); sw=R.learnDocumentSwaps(full); print('learned in',round(time.perf_counter()-t,1),'s:',[(a.replace(R.REPH_MARK,'R'),b.replace(R.REPH_MARK,'R'),n) for a,b,n in sw])
B=json.load(open('/root/pdfs/bench.json'))
H=T=Hr=0
R.setDocumentSwaps(sw,'ew')
for pg in B['ew4all.pdf']:
    d=BA.Doc(); d.broken=True
    out='\n'.join(d.read(l) for l in pg['pdfium'].splitlines())
    h,t=BA.match(out,pg['ocr']); H+=h; T+=t; Hr+=BA.match(pg['pdfium'],pg['ocr'])[0]
print(f'ew4all raw {Hr/T:.1%} -> repaired {H/T:.1%}')
pg=B['ew4all.pdf'][1]
for l in pg['pdfium'].splitlines()[:25]:
    if l.strip(): print('PDF :',l.strip()[:70]); print('READ:',R.repair(l,broken=True).strip()[:70])
