# Signs a PDF viewer puts one letter too far to the right, Preeti words inside Unicode lines, and
# correct text that must stay as it is. Run from the source folder: python tests/test_moved_signs.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'addon', 'globalPlugins', 'nepaliReader'))
import neLexicon
neLexicon.load()
import devanagariRepair as DR
import glyphOrder as G
DR.loadConfusions()

failures = 0


def check(name, got, want):
	global failures
	ok = got == want
	if not ok:
		failures += 1
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))


# the line from the report (Chrome PDF, 25 November 2026): the first word is the end of प्रदान
REPORTED = "fg गरे वापत as+} कोडको अनसु ारकोकमिशन वा सवे ा zN's लगाउन सक्नछे । as+} लेसमय समयमा निर्धारण ण, थप वा परिमाजर्न गरेअनसु ारकोशल्ुक"
WANT = "fg गरे वापत बैंक कोडको अनुसारको कमिशन वा सेवा शुल्क लगाउन सक्नेछ । बैंकले समय समयमा निर्धारण, थप वा परिमार्जन गरेअनुसारको शुल्क"
check('reported line, PDF', DR.repairIn(REPORTED, pdf=True), WANT)
check('reported line, damaged PDF', DR.repairIn(REPORTED, pdf=True, brokenDoc=True), WANT)
check('reported line copied into typed text', DR.repairTyped(REPORTED), WANT)

# one word at a time: the sign or reph goes back one letter
for broken, right in [('शल्ुक', 'शुल्क'), ('सवेा', 'सेवा'), ('अनसुार', 'अनुसार'), ('सक्नछे', 'सक्नेछ'),
		('परिमाजर्न', 'परिमार्जन'), ('निणर्ायक', 'निर्णायक'), ('मलुकु', 'मुलुक'), ('गतदेखेि', 'गतेदेखि'),
		('पवूर्ाधार', 'पूर्वाधार'), ('हदुँै', 'हुँदै'), ('दवुै', 'दुवै'), ('बकैं', 'बैंक')]:
	fx = G.fixWord(broken, None, allowValid=True)
	check('moved: %s' % broken, fx and fx[0], right)

# Preeti keys inside a Unicode line, moved the same way
for keys, right in [("zN's", 'शुल्क'), ('as+}', 'बैंक'), ("z'Ns", 'शुल्क'), ('a}+s', 'बैंक')]:
	r = G.preetiToken(keys, G._preetiConverter)
	check('Preeti in a Unicode line: %s' % keys, r and r[0], right)
# English and numbers inside a Unicode line stay
for latin in ['ATM', 'SMS', 'km', 'Rs', 'PDF', 'www.nrb.org.np', '2024', 'Email', 'the', 'NIC', 'KYC']:
	check('kept in a Unicode line: %s' % latin, G.preetiToken(latin, G._preetiConverter), None)

# correct text is not changed, in a PDF or typed
CORRECT = [
	'नेपाल सरकारले आगामी आर्थिक वर्षको बजेट सार्वजनिक गरेको छ ।',
	'उनीहरू घर फर्केका छन् ।',
	'नसकेको दिनुभयो करिव करिव',          # 2.1.0 swapped letters: सिकेको, दर्नुभयो, विवि विवि
	'बैंकले शुल्क लिन सक्नेछ',
	'कोभिड19को',
	'ँ ं ः',                             # a list of the signs in a lesson
	'पूर्वसूचना र पूर्वतयारी',           # compounds the PDF writes as one word
	'आतिथ्यतामा अध्यक्षतामा तत्कालका',   # 2.1.0 read आतिथ्य तामा, अध्यक्ष तामा, तत्काल
	'पञ्चासेमा अत्रौलीटारमा',            # place names: not cut
	'गरेपछि',                            # web pages: once read गतेपछि
]
for t in CORRECT:
	check('correct, PDF: ' + t, DR.repairIn(t, pdf=True), t)
	check('correct, typed: ' + t, DR.repairTyped(t), t)

# signs drawn twice for a bold look
for broken, right in [('सिर्जिित', 'सिर्जित'), ('रेेकर्डड', 'रेकर्ड'), ('सम्पूूर्णण', 'सम्पूर्ण'), ('दुुर्गगम', 'दुर्गम'), ('कुुदुु', 'कुदु')]:
	check('drawn twice: ' + broken, DR.repair(broken), right)

# a sign left over from a lost letter is not glued to the word before it
check('lost letter: संसदले ो ऐन', 'संसदलेो' in DR.repairIn('संसदले ो ऐन बनाएको छ', pdf=True), False)

# the document's pattern: three proven words teach it
p = G.Pattern()
for w in ['शल्ुक', 'सवेा', 'अनसुार']:
	fx = G.fixWord(w, p, allowValid=True)
	p.note(fx[1])
check('pattern learned after three words', p.shows('mark'), True)
p2 = G.Pattern()
p2.note(('forced', 'mark'))
check('a guess teaches nothing', p2.shows('mark', 1), False)

print('\n%d failed' % failures if failures else '\nall passed')
sys.exit(1 if failures else 0)
