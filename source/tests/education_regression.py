"""Real PDF regression: python tests/education_regression.py /path/to/kpkjoxrppjm1y2jt.pdf"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / 'addon/globalPlugins/nepaliReader' if (ROOT / 'addon/globalPlugins/nepaliReader').exists() else (ROOT / 'globalPlugins/nepaliReader' if (ROOT / 'globalPlugins/nepaliReader').exists() else ROOT / 'source/addon/globalPlugins/nepaliReader')
sys.path.insert(0, str(MODULES))
import pdfText as pt, neLexicon as lex, detector as det, glyphRefs
lex.load();det.loadDictionary();glyphRefs.load()
if len(sys.argv) < 2:
    print("Usage: python education_regression.py <pdf-path>")
    sys.exit(1)
data=Path(sys.argv[1]).read_bytes()
result=[]
for pages in [2,None]:
 i=pt.DocIndex.build(data,maxPages=pages,detector=det,isWord=lex.isWord,timeLimit=90)
 for source,want in [('प्रस्िावना','प्रस्तावना'),('सवनसाधारण','सर्वसाधारण')]:
  found=[w[0] for w in i.words if w[3]==source]
  assert found and all(w==want for w in found),(pages,source,found)
 result.append({'pages':i.stats['pages'],'words':i.stats['words'],'target_cases':'passed'})
print(json.dumps(result,ensure_ascii=False,indent=2))
