# Nepali laws as published (Nepal Law Commission, Supreme Court, national park offices), read from
# the PDF file the way NVDA reads them when the file is found. Every PDF with text must read as
# words; lines checked against the printed page must read exactly so.
# Run from the source folder with NEPALI_TEST_LAWS set to the folder of law PDFs
# ("NepaliReader test PDFs\laws"):  python tests/test_law_pdfs.py
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'addon', 'globalPlugins', 'nepaliReader'))
folder = os.environ.get('NEPALI_TEST_LAWS', '')
if not os.path.isdir(folder):
	print('skip: set NEPALI_TEST_LAWS to the folder of law PDFs')
	sys.exit(0)
import neLexicon
neLexicon.load()
import detector
detector.loadDictionary()
import glyphRefs
glyphRefs.load()
import glyphOrder
glyphOrder.setDictionary(neLexicon.isWord)
glyphOrder.loadFrequencies()
import pdfText

failures = 0

# checked against the printed pages
PRINTED = {
	'भ्रष्टाचार-निवारण-ऐन-२०५९': ['भ्रष्टाचार निवारण ऐन, २०५९', 'भ्रष्टाचार निवारणका सम्बन्धमा समयानुकूल कानुनी व्यवस्था गर्न बनेको ऐन'],
	'मुलुकी-अपराध-संहिता-२०७४': ['तहको पूर्ण वा अधिकांश स्वामित्व वा नियन्त्रण भएको सङ्गठित संस्थाको सम्पत्ति वा सार्वजनिक सम्पत्तिको सुरक्षाका लागि अधिकार प्राप्त अधिकारीको आदेशबाट खटिएको सुरक्षाकर्मीले'],
	'राष्ट्रिय-निकुञ्ज-तथा-वन्यजन्तु-संरक्षण-ऐन-२०२९': ['(ग) “वन्यजन्तु आरक्ष” भन्नाले वन्यजन्तु सम्पदा र तिनीहरुको वासस्थानको संरक्षण तथा व्यवस्था गर्न छुट्याइएको क्षेत्रलाई सम्झनु पर्छ ।'],
	'हिमाली-राष्ट्रिय-निकुञ्ज-नियमावली-२०३६': ['(ख) कुनै भूभाग कब्जा गर्न,'],
}
# (font tables re-encoded by Ghostscript: read well enough to follow, not yet as printed)
LOWER = {'हिमाली-राष्ट्रिय-निकुञ्ज-नियमावली-२०३६': 80.0, 'आर्थिक-ऐन-२०८३': 85.0, 'मूल्य-अभिवृद्धि-कर-ऐन-२०५२': 85.0}


def known(w):
	return neLexicon.isWord(w) or glyphOrder.frequency(w) >= 2


def check(name, ok, detail=''):
	global failures
	if not ok:
		failures += 1
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     ' + detail))


for name in sorted(os.listdir(folder)):
	if not name.lower().endswith('.pdf'):
		continue
	t = time.time()
	idx = pdfText.DocIndex.build(open(os.path.join(folder, name), 'rb').read(), detector=detector, isWord=neLexicon.isWord, timeLimit=900)
	text = ' '.join((f if f is not None else k) or '' for f, a, e, k in idx.words)
	words = [w.strip('।,;:()‘’“”"\'?!-–—.०१२३४५६७८९0123456789/') for w in text.split()]
	words = [w for w in words if re.fullmatch('[ऀ-ॿ]{2,}', w)]
	short = re.sub(r'^nepali-law-|(-snp|-supremecourt)?\.pdf$', '', name)
	if not words:
		print('     %s: no text (a scanned PDF: use an OCR add-on)' % short)
		continue
	rate = 100.0 * sum(known(w) for w in words) / len(words)
	check('%s: %.1f%% of %d words known, %.1f s' % (short, rate, len(words), time.time() - t), rate >= LOWER.get(short, 93.0))
	# a word cut after a half letter (भ्रष् टाचार): the two pieces make a known word, the first alone does not
	split = [m.group(0) for m in re.finditer(r'([\u0900-\u097f]+्) ([क-ह][\u0900-\u097f]*)', text) if not known(m.group(1)) and known(m.group(1) + m.group(2))]
	check('%s: no word cut after a half letter' % short, len(split) <= 3, str(split[:5]))
	for line in PRINTED.get(short, []):
		check('%s: reads as printed: %s' % (short, line[:40]), line in text, text[max(0, text.find(line[:12]) - 20):text.find(line[:12]) + len(line) + 20])

print('\n%d failed' % failures if failures else '\nall passed')
sys.exit(1 if failures else 0)
