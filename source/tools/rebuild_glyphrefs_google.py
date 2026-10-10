import sys, os, glob, json, zlib, hashlib, collections
sys.path.insert(0,'tests/fakenvda'); import setup_fake
sys.path.insert(0,'addon/globalPlugins')
from nepaliReader import sfnt, glyphRefs
old=json.loads(zlib.decompress(open('addon/globalPlugins/nepaliReader/glyphRefs.dat','rb').read()).decode())['fonts']
new=[]; seen=set()
for p in sorted(glob.glob('/tmp/claude-0/w/gf/ttf/*.ttf')):
    data=open(p,'rb').read()
    for face in range(sfnt.faceCount(data)):
        try:
            f=sfnt.Font(data,face); fam,sub,full,ps=f.names()
            if not any(0x900<=c<=0x97f for c in f.cmap()): continue
            upm,rows=sfnt.referenceTable(f)
        except Exception as e:
            print('skip',p,e); continue
        key=hashlib.md5((glyphRefs.norm(fam)+json.dumps(rows)).encode()).hexdigest()
        if key in seen: continue
        seen.add(key)
        new.append({'family':glyphRefs.norm(fam),'ps':glyphRefs.norm(ps or fam),'style':glyphRefs.styleOf(sub+' '+ps),'upm':upm,
            'adv':[r[1] for r in rows],'str':[r[0] for r in rows],'hash':[r[2] for r in rows]})
newHash={}
for e in new:
    for s,h in zip(e['str'],e['hash']):
        if h and s: newHash.setdefault(h,s)
newFams=set(e['family'] for e in new)
fixed=0; dropped=0; keptOld=0
out=list(new)
for e in old:
    strs=list(e['str'])
    cnt=collections.Counter(s for s in strs if s)
    for i,(s,h) in enumerate(zip(strs,e['hash'])):
        if h in newHash:
            if newHash[h]!=s: strs[i]=newHash[h]; fixed+=1
        elif s and 'ृ' in s and cnt[s]>1:
            strs[i]=''; dropped+=1   # a reph that an old build labelled ृ: unknown rather than wrong
    e=dict(e); e['str']=strs
    # an old table identical in glyphs to a new one adds nothing
    if e['family'] in newFams and all((h in newHash) for h in e['hash'] if h):
        continue
    out.append(e); keptOld+=1
print('new tables',len(new),'old kept',keptOld,'old entries fixed',fixed,'dropped',dropped)
blob=zlib.compress(json.dumps({'fonts':out},ensure_ascii=False,separators=(',',':')).encode('utf-8'),9)
open(sys.argv[1],'wb').write(blob); print('bytes',len(blob))
