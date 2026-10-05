import sys, time, types
sys.path.insert(0,'tests/fakenvda'); import setup_fake as F
sys.path.insert(0,'addon/globalPlugins')
F.sys.modules['config'].conf.profiles=[{}]
import nepaliReader as NR, speech.speech as SS
p=NR.GlobalPlugin()
while not p._ready: time.sleep(0.05)
F.state['app']='chrome'; F.state['title']='Setopati - Google Chrome'
class D:
    def __init__(s,t): s.t=t; s.obj=types.SimpleNamespace(rootNVDAObject=types.SimpleNamespace(appModule=types.SimpleNamespace(appName='chrome')))
    def getTextWithFields(s,fc): return [s.t]
    text=property(lambda s:s.t)
    boundingRects=[]
for t in ['भनसुन गर्नुपर्छ र नेताको चाकडी गर्नुपर्छ!','उपेन्द्रबहादुर कार्कीले सरकारी जागिर खाने','काठमाडौं, असोज १९','Number: 58 Word Count: 278']:
    print(next(SS.getTextInfoSpeech(D(t))))
p.script_toggleNepaliMode(None); print(F.spoken[-1], next(SS.getTextInfoSpeech(D('भनसुन गर्नुपर्छ'))))
p.script_toggleNepaliMode(None); print(F.spoken[-1])
