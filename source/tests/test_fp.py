import sys, time, random, json; sys.path.insert(0,'tests/fakenvda'); import setup_fake as F
sys.path.insert(0,'addon/globalPlugins')
import nepaliReader as NR, speech.speech as SS, wordfreq
from npttf2utf.base.preetimapper import convert as toPreeti
p=NR.GlobalPlugin(); time.sleep(0.5)
FC,FF=F.FieldCommand,F.FormatField
class Doc:
    def __init__(s,f): s.f=f; s.obj=F.types.SimpleNamespace(windowClassName='_WwG', appModule=F.types.SimpleNamespace(appName='winword'))
    def getTextWithFields(s,fc): return list(s.f)
    boundingRects=[]
F.state['app']='winword'; F.state['title']='doc.docx - Word'
def say(t): return next(SS.getTextInfoSpeech(Doc([FC('formatChange',FF({'font-name':'Calibri'})),t])))
random.seed(9)
en=[w for w in wordfreq.top_n_list('en',60000) if w.isascii()]
lines=[l.strip() for l in open('tests/english.txt') if l.strip()]+[' '.join(random.sample(en,random.randint(1,12))) for _ in range(5000)]
conv=[(l,say(l)) for l in lines]; bad=[(l,o) for l,o in conv if len(o)>1]
print('English lines in Calibri converted:',len(bad),'of',len(lines)); [print('  ',b) for b in bad[:10]]
H=json.load(open('tests/heldout.json'))
pure=[w for w in H['hiHeldPreeti'] if w.isascii()]
pl=[' '.join(random.sample(pure,random.randint(2,8))) for _ in range(2000)]
miss=sum(1 for l in pl if len(say(l))==1)
print('Preeti lines in Calibri missed:',miss,'of',len(pl))
