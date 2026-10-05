import sys; sys.path.insert(0,'addon/globalPlugins/nepaliReader')
exec(open('tests/test_visual.py').read().split('stats={}')[0])
import visualScript as V
def feats(img):
    raw=img.convert('RGBA').tobytes('raw','BGRA'); w,h=img.size
    g=raw[1::4]; bg=max(set(g[::3]),key=g[::3].count)
    ink=g.translate(V._inkTable(bg,70)); rows=[ink[y*w:(y+1)*w] for y in range(h)]
    ys=[y for y in range(h) if 1 in rows[y]]; top,bot=ys[0],ys[-1]; rows=rows[top:bot+1]; H=len(rows)
    col=bytearray(w)
    for r in rows:
        for x,v in enumerate(r):
            if v: col[x]=1
    out=[]
    for l,r_ in V._segments(col,max(2,int(H*0.22))):
        W=r_-l
        if W<H*0.7: continue
        best=0
        for i in range(int(H*0.65)):
            seg=rows[i][l:r_]
            cov=sum(len(x) for x in seg.split(b'\x00') if len(x)>=max(3,H*0.35))/W
            best=max(best,cov)
        out.append(round(best,2))
    return out
import random
for kind,texts,fonts in (('deva',deva,deva_fonts),('latin',lat,lat_fonts)):
    vals=[]
    for text in texts:
        for font in fonts:
            for size in (11,13,16,20,26):
                vals+=feats(render(text,font,size,False,False))
    vals.sort(); n=len(vals)
    print(kind,n,'pct 1,5,10,50,90,95,99:',[vals[int(n*p)] for p in (0.01,0.05,0.1,0.5,0.9,0.95,0.99)])
print('---')
hiL=collections=None
import collections
c=collections.Counter(); d=collections.Counter()
for text in lat:
    for font in lat_fonts:
        for size in (13,16,20):
            f=feats(render(text,font,size))
            # map words
            ws=text.split()
            if f and max(f)>=0.85: c[(text[:30],font.split('/')[-1])]+=1
for text in deva:
    for font in deva_fonts:
        for size in (13,16,20):
            f=feats(render(text,font,size))
            low=[x for x in f if x<0.85]
            if low: d[(text[:20],font.split('/')[-1][:8],tuple(low))]+=1
print(c.most_common(25)); print(list(d.items())[:25])
