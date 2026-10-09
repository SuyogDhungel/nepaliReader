import sys, types, builtins
builtins._ = lambda s: s
def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class Filter:
    def __init__(self): self.h=[]
    def register(self,f): self.h.append(f)
    def unregister(self,f): self.h.remove(f)
    def apply(self,v,**kw):
        for f in self.h: v=f(v,**kw)
        return v
class LangChangeCommand:
    def __init__(self,lang): self.lang=lang
    def __repr__(self): return f'Lang({self.lang})'
class Sect(dict):
    def dict(self): return dict(self)
conf={'nepaliReader':Sect(enabled=True,pdfFile=True,mode='auto',encoding='preeti',autoDetectKruti=True,useFontNames=True,repairUnicode=True,switchLanguage=True,convertSpelling=True,visualCheck=True,webFontOnly=True,lastOnMode='auto',tesseractPath='',ocrLanguages='nep+hin+eng'),'documentFormatting':Sect(reportFontName=False)}
mod('addonHandler', initTranslation=lambda: None)
mod('globalCommands', GlobalCommands=type('GlobalCommands',(),{'__gestures':{}}))
mod('NVDAObjects', NVDAObject=type('NVDAObject',(),{}))
class Spec(dict): pass
mod('config', conf=type('C',(dict,),{'spec':Spec()})(conf))
state={'font':None,'fg':1,'app':'acrord32','title':'notice.pdf - Adobe Acrobat','line':'', 'pixels':None}
class FieldCommand:
    def __init__(self,c,f): self.command=c; self.field=f
    def __repr__(self): return f'FC({self.command},{dict(self.field) if self.field else None})'
class FormatField(dict): pass
class Rect:
    def __init__(s,l,t,w,h): s.left,s.top,s.width,s.height=l,t,w,h
class Info:
    def copy(self): return self
    def expand(self,u): pass
    @property
    def text(self): return state['line']
    @property
    def boundingRects(self):
        p=state['pixels']
        return [Rect(0,0,p[1],p[2])] if p else []
    def getTextWithFields(self,fc): return [FieldCommand('formatChange',{'font-name':state['font']})] if state['font'] else []
mod('textInfos', FieldCommand=FieldCommand, FormatField=FormatField, UNIT_CHARACTER='character', UNIT_LINE='line', UNIT_WORD='word', UNIT_PARAGRAPH='paragraph', POSITION_SELECTION='sel')
mod('api', getForegroundObject=lambda: types.SimpleNamespace(windowHandle=state['fg'], name=state['title']), getFocusObject=lambda: types.SimpleNamespace(windowClassName='X', appModule=types.SimpleNamespace(appName=state['app'])), getCaretPosition=lambda: Info(), getReviewPosition=lambda: Info(), getClipData=lambda: '', copyToClip=lambda t: None)
mod('globalPluginHandler', GlobalPlugin=type('GP',(),{'__init__':lambda s,*a,**k:None,'terminate':lambda s:None}))
mod('gui', guiHelper=None); mod('gui.guiHelper')
class NVDASettingsDialog: categoryClasses=[]
mod('gui.settingsDialogs', NVDASettingsDialog=NVDASettingsDialog, SettingsPanel=object)
class Menu:
    def __init__(s): s.items=[]
    def AppendCheckItem(s,i,l): it=types.SimpleNamespace(label=l,Check=lambda v: setattr(it,'checked',v),checked=False); s.items.append(it); return it
    def Append(s,i,l): it=types.SimpleNamespace(label=l); s.items.append(it); return it
    def AppendSubMenu(s,m,l): s.items.append((l,m)); return (l,m)
    def Remove(s,x): s.items.remove(x)
binds=[]
tray=types.SimpleNamespace(toolsMenu=Menu(), Bind=lambda ev,fn,item: binds.append((item,fn)))
sys.modules['gui'].mainFrame=types.SimpleNamespace(sysTrayIcon=tray, popupSettingsDialog=lambda *a: binds.append(('opened',a)))
mod('wx'); sys.modules['wx'].Menu=Menu; sys.modules['wx'].ID_ANY=-1; sys.modules['wx'].EVT_MENU='menu'
sys.modules['wx'].CallAfter=lambda f,*a: f(*a); sys.modules['wx'].CallLater=lambda ms,f,*a: f(*a)
mod('tones', beep=lambda *a: None); spoken=[]
mod('ui', message=lambda m: spoken.append(m))
mod('logHandler', log=types.SimpleNamespace(debug=print,info=print,debugWarning=lambda *a,**k: __import__('traceback').print_exc(),error=lambda *a,**k: (print('ERROR',a), __import__('traceback').print_exc()),exception=print))
mod('scriptHandler', script=lambda **kw: (lambda f: f))
sp=mod('speech'); sp.__path__=[]
def getTextInfoSpeech(info, useCache=True, formatConfig=None, unit=None, **kw):
    lang=None; out=[]
    for f in info.getTextWithFields(formatConfig or {}):
        if isinstance(f,FieldCommand):
            if f.command=='formatChange' and f.field.get('language')!=lang:
                lang=f.field.get('language'); out.append(('LANG',lang))
        elif isinstance(f,str): out.append(f)
    yield out
    return True
spm=mod('speech.speech', getTextInfoSpeech=getTextInfoSpeech); sp.getTextInfoSpeech=getTextInfoSpeech
spoken_menu=[]
def speak(seq,**kw): spoken_menu.append(seq)
spm.speak=speak; sp.speak=speak
say=mod('speech.sayAll'); say.SayAllHandler=types.SimpleNamespace(_getTextInfoSpeech=getTextInfoSpeech); sp.sayAll=say

import ctypes
class SB:
    def __init__(s,w,h): s.w,s.h=w,h
    def captureImage(s,l,t,w,h):
        raw=state['pixels'][0]; buf=(ctypes.c_ubyte*len(raw)).from_buffer_copy(raw); return buf
mod('screenBitmap', ScreenBitmap=SB)
mod('globalVars', appArgs=types.SimpleNamespace(configPath='/tmp/nvdacfg_fake'))
sys.modules['textInfos'].convertToCrlf = lambda t: t.replace('\n', '\r\n')
class _TI:
    def copyToClipboard(self, notify=False): return True
sys.modules['textInfos'].TextInfo = _TI
