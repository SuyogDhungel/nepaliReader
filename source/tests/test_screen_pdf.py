import sys, time, random, unicodedata; sys.path.insert(0,'tests/fakenvda'); import setup_fake as F
sys.path.insert(0,'addon/globalPlugins')
from PIL import Image, ImageDraw, ImageFont
import nepaliReader as NR, speech.speech as SS
from npttf2utf.base.preetimapper import convert as toPreeti
p=NR.GlobalPlugin(); time.sleep(0.8)
N=lambda s: unicodedata.normalize('NFC',s)
FONTS_NE=['/root/ref/gf/ofl/mukta/Mukta-Regular.ttf','/root/ref/gf/ofl/notosansdevanagari/NotoSansDevanagari[wdth,wght].ttf','/usr/share/fonts/truetype/freefont/FreeSerif.ttf']
FONTS_EN=['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf']
def px(text,fontp,size=15):
    f=ImageFont.truetype(fontp,size,layout_engine=ImageFont.Layout.RAQM); l,t,r,b=f.getbbox(text)
    img=Image.new('RGB',(max(r-l+12,20),int(size*1.7)),'white'); ImageDraw.Draw(img).text((6-l,int(size*0.3)),text,font=f,fill='black')
    return (img.convert('RGBA').tobytes('raw','BGRA'),img.width,img.height)
class Doc:
    def __init__(s,f,pix): s.f=f; s.pix=pix; s.obj=F.types.SimpleNamespace(windowClassName='AVL_AVView', appModule=F.types.SimpleNamespace(appName='acrord32'))
    def getTextWithFields(s,fc): return list(s.f)
    @property
    def boundingRects(s):
        F.state['pixels']=s.pix; return [F.Rect(0,0,s.pix[1],s.pix[2])]
F.state['app']='acrord32'; F.state['title']='notice.pdf - Adobe Acrobat Reader'
random.seed(11)
ne=[w for w in open('/root/ref/nedict/ne_words.txt',encoding='utf8').read().split('\n') if w]
sent=[l.strip() for l in open('tests/sentences_ne.txt',encoding='utf8') if l.strip()]
short=['म','र','छ','हो','त','न','यो','को','मा','ले','पनि','अब','ऊ','ओ','ए','भो','उ','अनि']
lines=sent+[' '.join(random.sample(ne,random.randint(1,6))) for _ in range(150)]+short
ok=0; bad=[]
for k,u in enumerate(lines):
    p._clearContext(); p._docs.clear(); p._visCache.clear()   # each line judged alone (worst case)
    pre=toPreeti(u)
    out=''.join(x for x in next(SS.getTextInfoSpeech(Doc([pre],px(u,FONTS_NE[k%3])))) if isinstance(x,str))
    if N(out)==N(u): ok+=1
    else: bad.append((u,pre,out))
print('untagged Preeti in a PDF, read alone:',ok,'of',len(lines))
for b in bad[:12]: print('   ',b)
eng=[l.strip() for l in open('tests/english.txt') if l.strip()]+['of','are','ease','am','Hi','OK','Page 3','is and']
ok=0; badE=[]
for k,e in enumerate(eng):
    p._clearContext(); p._docs.clear(); p._visCache.clear()
    out=''.join(x for x in next(SS.getTextInfoSpeech(Doc([e],px(e,FONTS_EN[k%2])))) if isinstance(x,str))
    if out==e: ok+=1
    else: badE.append((e,out))
print('English in a PDF kept:',ok,'of',len(eng), badE[:10])
