import asyncio, html, os, subprocess, base64, sys
from npttf2utf.base.preetimapper import convert as toPreeti
truth=open('truth.txt',encoding='utf8').read().split('\n')
R='/root/work/ref/'
FONTS={ # name -> file
 'Kalimati':'/root/work/Kalimati.ttf','Mangal':'/root/work/mangalb.ttf','Mukta':R+'Mukta-Regular.ttf','Hind':R+'Hind-Regular.ttf',
 'NotoSansDevanagari':R+'NotoSansDevanagari-Regular.ttf','NotoSerifDevanagari':R+'NotoSerifDevanagari-Regular.ttf','Rajdhani':R+'Rajdhani-Regular.ttf',
 'Poppins':R+'Poppins-Regular.ttf','TiroHindi':R+'TiroDevanagariHindi-Regular.ttf','Annapurna':R+'AnnapurnaSIL-Regular.ttf','Laila':R+'Laila-Regular.ttf',
 'Martel':R+'Martel-Regular.ttf','Kalam':R+'Kalam-Regular.ttf','Sarala':R+'Sarala-Regular.ttf','Karma':R+'Karma-Regular.ttf','Khand':R+'Khand-Regular.ttf',
 'Yantramanav':R+'Yantramanav-Regular.ttf','Halant':R+'Halant-Regular.ttf'}
LEG={'Preeti':'/root/work/preetihv.ttf','PCS':'/root/work/PCSNEPAL.TTF','Kantipur':'/root/work/KANTI.TTF','Untagged':'/root/work/preeti/untagged.ttf'}
os.makedirs('pdf',exist_ok=True)
def ff(path): return base64.b64encode(open(path,'rb').read()).decode()
preetiLines=[toPreeti(l) for l in truth[:40]]
open('truth_preeti.txt','w',encoding='utf8').write('\n'.join(truth[:40]))
async def chrome():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page()
        for name,path in list(FONTS.items())+list(LEG.items()):
            lines=preetiLines if name in LEG else truth
            body=''.join(f'<p>{html.escape(l)}</p>' for l in lines)
            await pg.set_content(f'<html><head><style>@font-face{{font-family:F;src:url(data:font/ttf;base64,{ff(path)})}} body{{font-family:F;font-size:13pt}}</style></head><body>{body}</body></html>')
            await pg.wait_for_timeout(300)
            await pg.pdf(path=f'pdf/chrome_{name}.pdf')
        await b.close()
asyncio.run(chrome())
def libre(name, family, lines):
    paras=''.join(f'<text:p text:style-name="P1">{html.escape(l)}</text:p>' for l in lines)
    doc=f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.text">
<office:font-face-decls><style:font-face style:name="{family}" svg:font-family="'{family}'" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"/></office:font-face-decls>
<office:automatic-styles><style:style style:name="P1" style:family="paragraph"><style:text-properties style:font-name="{family}" style:font-name-complex="{family}" style:font-name-asian="{family}" fo:font-size="13pt" style:font-size-complex="13pt"/></style:style></office:automatic-styles>
<office:body><office:text>{paras}</office:text></office:body></office:document>'''
    open(f'pdf/libre_{name}.fodt','w',encoding='utf8').write(doc)
    subprocess.run(['soffice','--headless','--convert-to','pdf','--outdir','pdf',f'pdf/libre_{name}.fodt'],capture_output=True,timeout=300)
fam={'Kalimati':'Kalimati','Mangal':'Mangal','Mukta':'Mukta','Hind':'Hind','NotoSansDevanagari':'Noto Sans Devanagari','NotoSerifDevanagari':'Noto Serif Devanagari','Rajdhani':'Rajdhani','Laila':'Laila','Kalam':'Kalam','Martel':'Martel'}
for n,f in fam.items(): libre(n,f,truth)
libre('Preeti','Preeti Heavy',preetiLines); libre('Kantipur','Kantipur',preetiLines); libre('PCS','PCS NEPALI',preetiLines)
def tex(engine, name, family):
    body='\n\n'.join(l.replace('%','\\%').replace('#','\\#').replace('&','\\&').replace('_','\\_').replace('$','\\$') for l in truth)
    src=f'''\\documentclass{{article}}\\usepackage{{fontspec}}\\setmainfont[Script=Devanagari{',Renderer=HarfBuzz' if engine=='lualatex' else ''}]{{{family}}}\\begin{{document}}{body}\\end{{document}}'''
    open(f'pdf/{engine}_{name}.tex','w',encoding='utf8').write(src)
    subprocess.run([engine,'-interaction=nonstopmode','-output-directory=pdf',f'pdf/{engine}_{name}.tex'],capture_output=True,timeout=300)
for n in ('Kalimati','Mukta','NotoSansDevanagari','Laila','Kalam'):
    tex('xelatex',n,fam[n]); tex('lualatex',n,fam[n])
import pymupdf
for n in ('Kalimati','Mukta','Laila'):
    story=pymupdf.Story(html=''.join(f'<p style="font-family:F">{html.escape(l)}</p>' for l in truth), user_css=f'@font-face{{font-family:F;src:url({os.path.basename(FONTS[n])})}}', archive=os.path.dirname(FONTS[n]))
    w=pymupdf.DocumentWriter(f'pdf/mupdf_{n}.pdf'); r=pymupdf.paper_rect('a4'); more=1
    while more:
        dev=w.begin_page(r); more,_=story.place(r+(36,36,-36,-36)); story.draw(dev); w.end_page()
    w.close()
print(sorted(f for f in os.listdir('pdf') if f.endswith('.pdf')))
