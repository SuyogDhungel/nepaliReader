import sys, time; sys.path.insert(0,'tests/fakenvda'); import setup_fake as F
sys.path.insert(0,'addon/globalPlugins')
from PIL import Image, ImageDraw, ImageFont
import nepaliReader as NR, speech.speech as SS, speech.sayAll as SA
FC, FF = F.FieldCommand, F.FormatField
p=NR.GlobalPlugin(); time.sleep(0.5)
class Doc:
    def __init__(s, fields, pixels=None):
        s.fields=fields; s.obj=F.types.SimpleNamespace(windowClassName='AVL_AVView', appModule=F.types.SimpleNamespace(appName=F.state['app'])); s.pixels=pixels
    def getTextWithFields(s, fc): return list(s.fields)
    @property
    def boundingRects(s):
        if not s.pixels: return []
        F.state['pixels']=s.pixels; return [F.Rect(0,0,s.pixels[1],s.pixels[2])]
def speakDoc(fields, pixels=None, via=None):
    fn = via or SS.getTextInfoSpeech
    return next(fn(Doc(fields,pixels)))
def font(n): return FC('formatChange', FF({'font-name':n}))
def px(uni, fontp='/root/ref/gf/ofl/mukta/Mukta-Regular.ttf'):
    f=ImageFont.truetype(fontp,16,layout_engine=ImageFont.Layout.RAQM); l,t,r,b=f.getbbox(uni)
    img=Image.new('RGB',(r-l+12,26),'white'); ImageDraw.Draw(img).text((6-l,4),uni,font=f,fill='black')
    return (img.convert('RGBA').tobytes('raw','BGRA'),img.width,img.height)
def fresh(): p._clearContext(); p._visCache.clear(); p._webCheckTime=0
DJ='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
print('== Menus / dialogs / NVDA messages: not touched (no hook on speech.speak)')
SS.speak(['Preferences', 'submenu', 'Tools']); print('   ', F.spoken_menu[-1])
print('== Word with fonts')
fresh(); print('   Preeti font      ', speakDoc([font('Preeti'),'g]kfn ;/sf/ of are d 5']))
print('   Calibri font     ', speakDoc([font('Calibri'),'Office of the Prime Minister']))
print('   mixed runs       ', speakDoc([font('Calibri'),'Date: ',font('Preeti'),'@)*! ;fn',font('Calibri'),' (2024)']))
print('   Kruti Dev font   ', speakDoc([font('Kruti Dev 010'),'esjk uke usgy gSA']))
print('   Calibri Preeti-looking stays', speakDoc([font('Calibri'),'g]kfn ;/sf/']))
print('   char nav Preeti f', speakDoc([font('Preeti'),'f']))
print('== PDF without font names')
fresh(); print('   Preeti line      ', speakDoc(['g]kfn ;/sf/, lzIff dGqfno'], px('नेपाल सरकार, शिक्षा मन्त्रालय')))
print('   short word ctx   ', speakDoc(['of'], None), speakDoc(['l'], None))
fresh(); print('   short Preeti, screen says Nepali', speakDoc(['/fd ag'], px('राम बन')))
fresh(); print('   English, screen says English', speakDoc(['Report of the committee'], px('Report of the committee',DJ)))
fresh(); print('   English no screen ', speakDoc(['Report of the committee']))
fresh(); print('   broken Unicode    ', speakDoc(['िशक्षा मन्त्रालय ि क']))
print('== Web page (Chrome)')
F.state['app']='chrome'; F.state['title']='Facebook - Google Chrome'; fresh()
print('   no font, Preeti-looking', speakDoc(['g]kfn ;/sf/'], px('नेपाल सरकार')))
print('   Segoe UI unicode', speakDoc([font('Segoe UI'),'नमस्ते साथी']))
print('   Preeti font css ', speakDoc([font('Preeti, sans-serif'),'g]kfn']))
F.state['title']='notice.pdf - Google Chrome'; fresh()
print('   PDF in Chrome   ', speakDoc(['g]kfn ;/sf/, lzIff dGqfno']))
F.state['app']='acrord32'
print('== say all uses the hook:', SA.SayAllHandler._getTextInfoSpeech is SS.getTextInfoSpeech)
p.script_cycleMode(None); p.script_cycleMode(None); print('== mode off', F.conf['nepaliReader']['mode'], speakDoc([font('Preeti'),'g]kfn'])); p.script_cycleMode(None)
t=time.perf_counter()
for i in range(3000): speakDoc(['g]kfn ;/sf/, lzIff dGqfno '+str(i%50)])
print('ms per line (no font)', round((time.perf_counter()-t)/3000*1000,3))
t=time.perf_counter()
for i in range(3000): speakDoc([font('Preeti'),'g]kfn ;/sf/, lzIff dGqfno '+str(i%50)])
print('ms per line (Preeti font)', round((time.perf_counter()-t)/3000*1000,3))
p.terminate(); print('unhooked', SS.getTextInfoSpeech is F.getTextInfoSpeech, SA.SayAllHandler._getTextInfoSpeech is F.getTextInfoSpeech)
print('== Word, Preeti keys typed in Calibri (user test)')
p2=NR.GlobalPlugin(); time.sleep(0.3); fresh()
print('   ', next(SS.getTextInfoSpeech(Doc([font('Calibri (Body)'),'d]/f] gfd']))))
print('   English in Calibri:', next(SS.getTextInfoSpeech(Doc([font('Calibri'),'my name is Suyog. Of course we are here.']))))
print('   ASCII in Mangal   :', next(SS.getTextInfoSpeech(Doc([font('Mangal'),'g]kfn']))))
print('== Tools menu:', [x[0] for x in F.tray.toolsMenu.items if isinstance(x,tuple)], [i.label for i in F.tray.toolsMenu.items[-1][1].items])
item=F.tray.toolsMenu.items[-1][1].items[0]; fn=[f for it,f in F.binds if it is item][0]
fn(None); print('   after toggle: mode', F.conf['nepaliReader']['mode'], 'checked', item.checked, F.spoken[-1])
print('   reading while off:', next(SS.getTextInfoSpeech(Doc([font('Preeti'),'g]kfn']))))
fn(None); print('   after toggle: mode', F.conf['nepaliReader']['mode'], 'checked', item.checked, F.spoken[-1])
p2.terminate(); print('   menu removed:', not any(isinstance(x,tuple) and x[0]=='&Nepali Reader' for x in F.tray.toolsMenu.items))
print('== Word line split by spelling-error marks (user test /fd]n] eft vfof])')
p3=NR.GlobalPlugin(); time.sleep(0.5); fresh()
F.state['app']='winword'; F.state['title']='Document2 - Word'
cal=lambda **k: FC('formatChange', FF({'font-name':'Calibri (Body)', **k}))
fields=[cal(),'/',cal(**{'invalid-spelling':True}),'fd]n]',cal(),' eft ',cal(**{'invalid-spelling':True}),'vfof]']
print('   ', next(SS.getTextInfoSpeech(Doc(fields))))
print('== Broken PDF (Chrome), lines from the flood report')
F.state['app']='chrome'; F.state['title']='Rasuwa-Bhotekoshi_Flood_Report_2083_Asoj_17.pdf - Google Chrome'; p3._webCheckTime=0
for line in ['रााष्ट्रि�िय वि�पद्् जोोखि�म न्यूनीूीकरण तथाा व्यवस्थाापन प्रााधि�करण','सिं ंहदरबाार, कााठमााडौंं�','मुख्य घटनााहरू ु','कुु ल']:
    print('   ', next(SS.getTextInfoSpeech(Doc([line]))))
p3.terminate()
