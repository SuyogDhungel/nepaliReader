# What the document itself says comes first: the PDF file's own text is not replaced by guesses,
# English typed in an editor stays English, and units and English in brackets stay English in a
# line with no font name. Run from the source folder: python tests/test_actual_content.py
# With NEPALI_TEST_PDFS set to a folder holding situation-report-2083-asoj.pdf and
# hydrology-white-paper-2083.pdf, the two real PDFs are read as well.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'addon', 'globalPlugins', 'nepaliReader'))
import neLexicon
neLexicon.load()
import detector
detector.loadDictionary()
import pdfText

failures = 0


def check(name, got, want):
	global failures
	ok = got == want
	if not ok:
		failures += 1
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))


def converted(line, enc='preeti'):
	return detector.convertMixed(line, lambda t: __import__('legacyFonts').convert(t, enc) or t, encoding=enc)


# a letter or two alone is no evidence of Preeti (in an editor "e" was read भ, "g" न)
for w in ['e', 'g', 'x', 'k']:
	check('alone, not Preeti: ' + w, detector.looksLegacy(w, 'preeti'), False)
	check('in a Preeti document: ' + w, detector.looksLegacy(w, 'preeti', context=True), True)
check('a Preeti word with a sign key: sf]', detector.looksLegacy('sf]', 'preeti'), True)

# units after numbers and English in brackets stay English in a line with no font name
check('units', converted("g]kfndf 1 in jf 2 in sf] k|of]u"), 'नेपालमा 1 in वा 2 in को प्रयोग')
check('English in brackets', converted("cWofo 1 sf] cGtu{t (Section 1 of)"), 'अध्याय 1 को अन्तर्गत (Section 1 of)')
check('title in brackets', '(Chief Executive Officer)' in converted("k|d'v (Chief Executive Officer) sf] a}7s"), True)
check('Preeti in brackets is converted', converted("k|d'v -g]kfn_ sf] a}7s"), 'प्रमुख (नेपाल) को बैठक')

# a quote mark at the start of a Preeti word is a quote (no word begins with ू, ु or ँ), and
# the same mark at the end of that word or phrase closes it; with the Preeti font named, the
# glyphs are read as the font draws them
import legacyFonts
check('quoted word', legacyFonts.convert('"g]kfn"'), '"नेपाल"')
check('quoted phrase', legacyFonts.convert('“g]kfn a}+s” sf] k|ltj]bg'), '“नेपाल बैंक” को प्रतिवेदन')
check('u sign inside a word stays', legacyFonts.convert("k|d'v"), 'प्रमुख')
check('font named Preeti: as drawn', legacyFonts.convert('"g]kfn"', trusted=True), 'ूनेपालू')

# a sign written twice in a row is read once (not a guess: Unicode never has it twice)
check('doubled signs', pdfText._undouble('तथाा असोोज न्यूूनीीकरण'), 'तथा असोज न्यूनीकरण')
check('nothing doubled', pdfText._undouble('कुल ०२ प्रतिवेदन'), 'कुल ०२ प्रतिवेदन')

# real PDFs: the file's own text, not dictionary guesses
folder = os.environ.get('NEPALI_TEST_PDFS')
if folder and os.path.isdir(folder):
	import glyphRefs
	glyphRefs.load()
	try:
		import glyphOrder
		glyphOrder.setDictionary(neLexicon.isWord)
	except ImportError:
		pass
	for name, want in [
		('situation-report-2083-asoj.pdf', 'ले जिल्ला प्रशासन कार्यालय, जिल्ला तथा राष्ट्रिय आपत्कालीन कार्य सञ्चालन केन्द्रहरूबाट प्राप्त विवरणका आधारमा तयार गरेको हो।'),
		('hydrology-white-paper-2083.pdf', 'नियमावली, २०८३ को नियम ५ को उपनियम १ को अनुसूची २ अनुसार हाल कृषि वन तथा पर्यावरण मन्त्रालय अन्तर्गत परेकोले जल विज्ञान तर्फको कार्यहरूलाई साबिककै ऊर्जा जलस्रोत तथा सिंचाइ मन्त्रालयबाट'),
	]:
		path = os.path.join(folder, name)
		if not os.path.exists(path):
			print('skip ' + name)
			continue
		idx = pdfText.DocIndex.build(open(path, 'rb').read(), detector=detector, isWord=neLexicon.isWord, timeLimit=300)
		text = ' '.join((f if f is not None else k) for f, a, e, k in idx.words)
		check('PDF file reading: ' + name, want in text, True)
else:
	print('skip: set NEPALI_TEST_PDFS to the "NepaliReader test PDFs" folder to read the real PDFs')

print('\n%d failed' % failures if failures else '\nall passed')
sys.exit(1 if failures else 0)
