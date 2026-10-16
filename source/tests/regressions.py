"""Offline regression checks; run python tests/regressions.py [fixture-directory].
Optional document checks require the fixture PDFs described in doc/en/validation.txt.
No NVDA hooks are installed by these tests.
"""
import sys,unittest,random,json,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODULES = ROOT / 'addon/globalPlugins/nepaliReader' if (ROOT / 'addon/globalPlugins/nepaliReader').exists() else (ROOT / 'globalPlugins/nepaliReader' if (ROOT / 'globalPlugins/nepaliReader').exists() else ROOT / 'source/addon/globalPlugins/nepaliReader')
sys.path.insert(0,str(MODULES))
import detector as det,legacyFonts as lf,devanagariRepair as dr,neLexicon as lex,pdfText as pt,glyphRefs
lex.load();det.loadDictionary();dr.loadConfusions();glyphRefs.load()
FIXTURES=Path(sys.argv.pop(1)) if len(sys.argv)>1 else None

def index_for(words):
 i=pt.DocIndex();i.starts=[];parts=[];p=0
 for fixed,shown in words:
  i.starts.append(p);parts.append(shown);p+=len(shown)
 i.B=''.join(parts);i.words=[(fixed,None,None,shown) for fixed,shown in words];i.lineStart=[True]*len(words);i._buildF();return i

class Regressions(unittest.TestCase):
 def test_symbol_markers_are_separate_from_words(self):
  from types import SimpleNamespace
  for family in ['ABCDEE+Webdings','Wingdings 2','Symbol']:
   sym=SimpleNamespace(baseFont=family,legacy=None,truth={},text=lambda c:'\uf060')
   nep=SimpleNamespace(baseFont='Kalimati',legacy=None,truth={1:'त'},text=lambda c:'ि')
   def g(f,x):return (f,1,x,100,12,6,None)
   for glyphs in [[g(sym,0),g(nep,6)],[g(nep,0),g(sym,6)],
                  [g(nep,6),g(sym,0),g(nep,12)]]:
    words=pt._words(glyphs,0)
    for w in words:
     self.assertEqual(len({pt._isSymbolFont(g[0]) for g in w.glyphs}),1)
 def test_symbol_font_not_inferred_as_nepali(self):
  from types import SimpleNamespace
  f=SimpleNamespace(baseFont='Webdings',legacy=None,used={1},truth={},weak=set(),text=lambda c:'\uf060')
  pt._inferFonts([f],[],lambda w:True,0)
  self.assertFalse(hasattr(f,'inferred'))
  w=pt.Word((0,True));w.glyphs=[(f,1,0,0,12,6,None)]
  self.assertIsNone(pt._wordTexts(w)[1])
  f.text=lambda c:'§'
  self.assertEqual(pt._wordTexts(w)[1],'§')
 def test_legacy_symbol_name_not_isolated(self):
  from types import SimpleNamespace
  self.assertFalse(pt._isSymbolFont(SimpleNamespace(baseFont='Symbol',legacy='preeti')))
 def test_all_modules_parse(self):
  for p in MODULES.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
 def test_anagrams_are_not_matches(self):
  for a,b in [('कलम','कमल'),('कमल','कलम'),('नाम','मान'),('सागर','सराग')]:
   with self.subTest(a=a,b=b):self.assertIsNone(index_for([(a,a)]).lookup(b))
 def test_displaced_vowels_still_match(self):
  i=index_for([('प्रमुख','प्रमुख')]);self.assertEqual(i.lookup('प्रमखु'),[('प्रमुख',True)])
 def test_conflicting_source_needs_position(self):
  i=index_for([('कमल','कलल'),('कलम','कलल')]);self.assertIsNone(i.lookup('कलल'))
  self.assertEqual(i.spanAt('कलल कलल',0,3),[('कमल',True)])
  self.assertEqual(i.spanAt('कलल कलल',4,3),[('कलम',True)])
  self.assertIsNone(i.charAt('कलल',0))
 def test_conflicting_token_fallback_abstains(self):
  i=index_for([('कमल','कलल'),('कलम','कलल')]);self.assertIsNone(i._tokens('कलल'))
 def test_english_words_preserved(self):
  for text in ['topographic','recruitable','unstatable','unimpartable','recollectable','ao','la','lu','eu','nu','stable','graphicDesign','tablecloth']:
   for ctx in [False,True]:
    with self.subTest(text=text,ctx=ctx):self.assertEqual(det.convertMixed(text,lf.preetiFamilyToUnicode,context=ctx),text)
 def test_english_syntax_and_symbols(self):
  for t in ['Budget (2026): Rs. 1,250.50','!@','&&','##','*','PDF API OTP ID URL','const value = 5;','https://example.org/file.pdf','C:\\Users\\Suyog\\report.pdf','suyog@example.org']:
   self.assertEqual(det.convertMixed(t,lf.preetiFamilyToUnicode),t)
 def test_confirmed_legacy_symbols_remain_supported(self):
  self.assertEqual(det.convertMixed('g]kfn !@',lf.preetiFamilyToUnicode),'नेपाल १२')
 def test_cross_script_role_boundary(self):
  self.assertEqual(det.cleanGluedTokens('नेपालheading'),'नेपाल heading')
 def test_unicode_conjuncts_not_numbers(self):
  for t in ['ज्ञ','द्द','द्ध','क ख ग ज्ञ','ज्ञ ज्ञ','ज्ञ.']:
   self.assertEqual(dr.repair(t,False),t);self.assertEqual(dr.repair(t,True),t)
 def test_clean_unicode_and_brackets(self):
  for t in ['नेपालका]','९क०','क० ','अध्ययन---प्रतिवेदन','कमल कलम','रु. १,२५०.५०']:
   self.assertEqual(dr.cleanShuffled(t),t)
 def test_dictionary_phrase_protected(self):
  self.assertEqual(dr.repair('हत्त न पत्त',True),'हत्त न पत्त')
 def test_structural_repairs_still_work(self):
  for src,want in [('नााराायणीी','नारायणी'),('जि ल्ला','जिल्ला'),('आधारभतू तह','आधारभूत तह')]:
   self.assertEqual(dr.repair(src,True),want)
 def test_known_preeti_keys(self):
  for src,want in [('g]kfn','नेपाल'),('sdn','कमल'),('snd','कलम'),('1','ज्ञ'),('3','घ'),('6','ट'),('#','३'),('*','८'),('(','९'),(')','०'),('-s_','(क)'),('!@#$%^&*()','१२३४५६७८९०')]:
   self.assertEqual(lf.convert(src,'preeti',trusted=True),want)
 def test_pcs_number_row(self):
  self.assertEqual(lf.convert('1234567890','pcs',trusted=True),'१२३४५६७८९०')
  self.assertEqual(lf.convert('!@#$%^&*()','pcs',trusted=True),'ज्ञद्दघद्धछटठडढण्')
 def test_english_sample_1000(self):
  ws=sorted(w for w in det._ENGLISH_DICT if w and w.isascii() and w.isalpha())
  for t in random.Random(20261016).sample(ws,1000):
   self.assertEqual(det.convertMixed(t,lf.preetiFamilyToUnicode,context=True),t)
 def test_nepali_sample_1000(self):
  ws=sorted(w for w in lex._STEMS if any('\u0900'<=c<='\u097f' for c in w))
  for t in random.Random(20261016).sample(ws,1000):self.assertEqual(dr.repair(t,True),t)
 def test_all_stems_cleanup_preserved(self):
  for t in lex._STEMS:self.assertEqual(dr.cleanShuffled(t),t)
 def test_updated_document_swaps(self):
  try:
   dr.setDocumentSwaps([('a','b',1)],'test');dr.setDocumentSwaps([('a','c',2)],'test');self.assertEqual(dr._DOC_SWAPS,[('a','c',2)])
  finally:dr.setDocumentSwaps([],None)
 def test_ambiguous_lexical_repair_abstains(self):
  # Same stored piece maps to two known words; counts/order must not choose one.
  try:
   dr.setDocumentSwaps([('ल','म',9),('ल','र',8)],'ambiguous')
   self.assertIsNone(dr._decodeWord('कलल'))
  finally:dr.setDocumentSwaps([],None)
 def test_empty_font_text_not_index_error(self):
  from types import SimpleNamespace
  self.assertFalse(pt._isTrailingSign(SimpleNamespace(text=lambda c:'',truth={},legacy=None),1))

@unittest.skipUnless(FIXTURES,'Optional PDF fixture directory not supplied')
class Documents(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.indices={name:pt.DocIndex.build((FIXTURES/(name+'.pdf')).read_bytes(),detector=det,isWord=lex.isWord,timeLimit=45) for name in ['preeti-mixed','preeti-misnamed','unicode-corrupt','Gorkha-2078']}
 def test_preeti_and_misnamed_font_words(self):
  expected=['नेपाल','कमल','कलम','ज्ञ','ट','३','८','९','०','(क)','१२३४५६७८९०']
  for name in ['preeti-mixed','preeti-misnamed']:
   words=self.indices[name].words
   self.assertEqual([w[0] for w in words if w[2]],expected)
   for fixed,amap,enc,shown in words:
    if enc is None:self.assertEqual(fixed,shown)
 def test_corrupt_unicode_recovered(self):
  self.assertEqual([w[0] for w in self.indices['unicode-corrupt'].words],['कमल','कलम','नेपाल','सरकार'])
 def test_gorkha_cover_preserved(self):
  got=[w[0] or w[3] for w in self.indices['Gorkha-2078'].words[:16]]
  self.assertEqual(got,['गोरखा','नगरपालिकाको','स्थानीय','पाठ्यक्रम','२०७८','आधारभूत','तह','(कक्षा','४–८)','गोरखा','नगरपालिका','शिक्षा,','युवा','तथा','खेलकुद','शाखा'])
 def test_full_gorkha_processed(self):
  i=self.indices['Gorkha-2078'];self.assertEqual(i.stats['pages'],43);self.assertEqual(len(i.words),12318)
 def test_legacy_character_mapping(self):
  i=self.indices['preeti-misnamed'];line='PDF API 6 : 6 English 123'
  self.assertEqual(i.charAt(line,line.rfind('6')),'ट')
  self.assertEqual(i.charAt(line,line.find('6')),'6')
  line='PDF API !@#$%^&*() : !@#$%^&*() English 123'
  start=line.rfind('!@')
  self.assertEqual(''.join(i.charAt(line,start+k) or '' for k in range(10)),'१२३४५६७८९०')
 def test_number_row_font_variants(self):
  probe=FIXTURES/'font-probes.pdf'
  if not probe.exists():self.skipTest('Optional font probes absent')
  i=pt.DocIndex.build(probe.read_bytes(),detector=det,isWord=lex.isWord,timeLimit=15)
  got={(enc,shown):fixed for fixed,amap,enc,shown in i.words if enc}
  self.assertEqual(got[('pcs','1234567890')],'१२३४५६७८९०')
  self.assertEqual(got[('pcs','!@#$%^&*()')],'ज्ञद्दघद्धछटठडढण्')
  self.assertEqual(got[('fontasy','!@#$%^&*()')],'!@#$%^&*()')
  self.assertEqual(got[('kantipur','!@#$%^&*()')],'१२३४५६७८९०')
 def test_dump_restore_navigation(self):
  i=self.indices['preeti-misnamed'];j=pt.DocIndex.restore(i.dump())
  self.assertIsNotNone(j);self.assertEqual(i.words,j.words)
  line='PDF API 6 : 6 English 123';self.assertEqual(j.charAt(line,line.rfind('6')),'ट')

if __name__=='__main__':unittest.main(verbosity=2)
