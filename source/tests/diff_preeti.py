import sys, os, unicodedata, collections
sys.path.insert(0,'addon/globalPlugins/nepaliReader')
from legacyFonts import preetiFamilyToUnicode as P
import npttf2utf, wordfreq
from npttf2utf.base.fontmapper import FontMapper
from npttf2utf.base.preetimapper import convert as toPreeti
fm=FontMapper(os.path.join(os.path.dirname(npttf2utf.__file__),'map.json'))
words=[w for w in wordfreq.top_n_list('hi',20000) if all('ऀ'<=c<='ॿ' for c in w)]
N=lambda s: unicodedata.normalize('NFC',s)
stats=collections.Counter(); samples=collections.defaultdict(list)
for u in words:
    pre=toPreeti(u)
    mine=N(P(pre)); ref=N(fm.map_to_unicode(pre,'Preeti'))
    ok_rt = mine==N(u); ref_rt = ref==N(u)
    key=('mine_ok' if ok_rt else 'mine_bad')+'/'+('ref_ok' if ref_rt else 'ref_bad')
    stats[key]+=1
    if len(samples[key])<12: samples[key].append((u,pre,mine,ref))
print(len(words), dict(stats))
for k,v in samples.items():
    if k!='mine_ok/ref_ok':
        print('==',k)
        for x in v: print('  ',x)
