import sys; sys.path.insert(0,'addon/globalPlugins/nepaliReader')
exec(open('tests/test_visual.py').read().split('stats={}')[0])
import visualScript as V, collections
def line_feat(img, L=0.35, region=0.65):
    raw=img.convert('RGBA').tobytes('raw','BGRA'); w,h=img.size
    g=raw[1::4]; bg=max(set(g[::3]),key=g[::3].count)
    ink=g.translate(V._inkTable(bg,70)); rows=[ink[y*w:(y+1)*w] for y in range(h)]
    ys=[y for y in range(h) if 1 in rows[y]]; rows=rows[ys[0]:ys[-1]+1]; H=len(rows)
    col=bytearray(w)
    for r in rows:
        for x,v in enumerate(r):
            if v: col[x]=1
    inkW=col.count(1)
    best=0; by=0
    for i in range(int(H*region)):
        cov=sum(len(x) for x in rows[i].split(b'\x00') if len(x)>=max(3,H*L))/inkW
        if cov>best: best,by=cov,i
    above=sum(rows[i].count(1) for i in range(by))/max(1,sum(r.count(1) for r in rows))
    return round(best,2), round(above,2), H
res=collections.defaultdict(list)
for kind,texts,fonts in (('deva',deva,deva_fonts),('latin',lat,lat_fonts)):
    for text in texts:
        if len(text)<3: continue
        for font in fonts:
            for size in (11,13,16,20,26):
                b,a,H=line_feat(render(text,font,size))
                res[kind].append((b,a,text[:20],font.split('/')[-1][:10],size))
for k,v in res.items():
    bs=sorted(x[0] for x in v); n=len(bs)
    print(k,n,[bs[int(n*p)] for p in (0.01,0.03,0.05,0.1,0.5,0.9,0.95,0.97,0.99)])
print(sorted(res['latin'],key=lambda x:-x[0])[:15])
print(sorted(res['deva'])[:10])
print([x for x in res['latin'] if 0.6<=x[0]<0.99][:30])
