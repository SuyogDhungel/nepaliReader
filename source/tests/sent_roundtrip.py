import sys,unicodedata
sys.path.insert(0,'addon/globalPlugins/nepaliReader')
from legacyFonts import preetiFamilyToUnicode as P
from npttf2utf.base.preetimapper import convert as toPreeti
N=lambda s:unicodedata.normalize('NFC',s)
bad=0
for line in open('tests/sentences_ne.txt',encoding='utf8'):
    u=line.strip(); 
    if not u: continue
    pre=toPreeti(u); back=N(P(pre))
    if back!=N(u):
        bad+=1; print('X',u,'\n ',pre,'\n ',back)
print('bad',bad)
