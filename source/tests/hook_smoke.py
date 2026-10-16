"""Mock NVDA checks. This is not a Windows/NVDA end-to-end test."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
for fake_dir in [ROOT / 'tests/fakenvda', ROOT / 'fakenvda', ROOT / 'source/tests/fakenvda']:
	if fake_dir.exists():
		sys.path.insert(0, str(fake_dir))
		break
import setup_fake as fake
for plugin_dir in [ROOT / 'addon/globalPlugins', ROOT / 'globalPlugins', ROOT / 'source/addon/globalPlugins']:
	if plugin_dir.exists():
		sys.path.insert(0, str(plugin_dir))
		break
import nepaliReader as nr
nr.neLexicon.load();nr.detector.loadDictionary();nr.devanagariRepair.loadConfusions()
class Hooks(unittest.TestCase):
 def setUp(self):
  self.p=nr.GlobalPlugin.__new__(nr.GlobalPlugin);self.p._cache=nr._LRU()
  self.p._isPdfWindow=lambda o:False;self.p._isWebNonPdf=lambda o:False
  self.p._inContext=lambda:None;self.p._docState=lambda:nr._DocState();self.p._isBrokenDoc=lambda:False
 def test_attributed_runs(self):
  for font,text,want in [('Preeti','6 # * -s_','ट ३ ८ (क)'),('Calibri','topographic !@','topographic !@'),('Mangal','ज्ञ कमल कलम','ज्ञ कमल कलम')]:
   fields=[fake.FieldCommand('formatChange',{'font-name':font}),text]
   out=self.p._convertFieldList(SimpleNamespace(obj=SimpleNamespace()),fields,fake.conf['nepaliReader'])
   self.assertEqual(''.join(x for x in out if isinstance(x,str)),want)
 def test_font_attributed_digit_character(self):
  for font,src,want in [('Preeti','6','ट'),('Preeti','#','३'),('PCS NEPALI','6','६')]:
   fields=[fake.FieldCommand('formatChange',{'font-name':font}),src]
   info=SimpleNamespace(text=src,getTextWithFields=lambda c:fields,obj=SimpleNamespace())
   out=self.p._resolveCharacter(info,{},fake.conf['nepaliReader'])
   self.assertEqual(''.join(x for x in out if isinstance(x,str)),want)
 def test_nonpdf_unicode_character_preserved(self):
  fields=[fake.FieldCommand('formatChange',{'font-name':'Mangal'}),'ज्ञ']
  info=SimpleNamespace(text='ज्ञ',getTextWithFields=lambda c:fields,obj=SimpleNamespace())
  out=self.p._resolveCharacter(info,{},fake.conf['nepaliReader'])
  self.assertEqual(''.join(x for x in out if isinstance(x,str)),'ज्ञ')
 def test_indexed_numeric_uses_line_position(self):
  class Idx:
   def spanAt(s,line,off,length):return [('ट',True)]
  self.p._lineContext=lambda info:('PDF 6',4)
  self.assertEqual(self.p._indexText(SimpleNamespace(text='6'),Idx(),'6'),'ट')
  self.assertIsNone(self.p._indexText(None,Idx(),'6'))
if __name__=='__main__':unittest.main(verbosity=2)
