import sys, time, random; sys.path.insert(0,'addon/globalPlugins/nepaliReader')
from PIL import Image, ImageDraw, ImageFont
import visualScript as V
R=ImageFont.Layout.RAQM
deva_fonts=['/root/ref/gf/ofl/mukta/Mukta-Regular.ttf','/root/ref/gf/ofl/notosansdevanagari/NotoSansDevanagari[wdth,wght].ttf','/usr/share/fonts/truetype/freefont/FreeSerif.ttf','/usr/share/fonts/truetype/freefont/FreeSans.ttf']
lat_fonts=['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf','/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf','/usr/share/fonts/truetype/freefont/FreeSerif.ttf']
deva=[l.strip() for l in open('tests/sentences_ne.txt',encoding='utf8') if l.strip()]+['म','छ','हो','र','पनि','के छ?','२०८१','ओ','ऊ','अ','उ','ए','इ','ठ','ड','ढ','झ','भ']
lat=[l.strip() for l in open('tests/english.txt') if l.strip()]+['THE TERM TEST','EFFECT','TTT','Hi','a','I','of','—','Total — 100','TELEPHONE','FIFTY','ZZZ TOP','Wi-Fi','i.e.']
def render(text,font,size,dark=False,underline=False):
    f=ImageFont.truetype(font,size,layout_engine=R)
    l,t,r,b=f.getbbox(text)
    W=r-l+12; H=int(size*1.6)
    img=Image.new('RGB',(max(W,10),H),(30,30,30) if dark else 'white'); d=ImageDraw.Draw(img)
    d.text((6-l,int(size*0.25)),text,font=f,fill=(230,230,230) if dark else (20,20,20))
    if underline: d.line((6,int(size*1.35),W-6,int(size*1.35)),fill=(0,0,200),width=1)
    return img
stats={}
bad=[]
t0=time.perf_counter(); n=0
for kind,texts,fonts in (('deva',deva,deva_fonts),('latin',lat,lat_fonts)):
    for text in texts:
        for font in fonts:
            for size in (11,13,16,20,26):
                for dark in (False,True):
                    for ul in (False,True):
                        img=render(text,font,size,dark,ul)
                        raw=img.convert('RGBA').tobytes('raw','BGRA')
                        r=V.classifyBgra(raw,img.width,img.height); n+=1
                        key=(kind,r); stats[key]=stats.get(key,0)+1
                        if (kind=='deva' and r=='latin') or (kind=='latin' and r=='deva'): bad.append((kind,text[:25],font.split('/')[-1],size,dark,ul,r))
print(stats, 'ms/img', round((time.perf_counter()-t0)/n*1000,2))
import collections
print(collections.Counter((b[0],b[1]) for b in bad).most_common(40))
