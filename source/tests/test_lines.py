# Lines of a PDF in Chrome as the page shows them: a heading that PDFium broke at a sign drawn below
# its letter ("पाठ", "्", "यक्रम") is one line, a page or heading begins a line of its own, word
# navigation takes the whole word; file names in titles and file URLs are read as their letters.
import sys, re, time, types
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
TI = sys.modules['textInfos']
VB = sys.modules['virtualBuffers']


class Story:
	"""NVDA's buffer of a Chrome PDF: text runs in region / heading / paragraph fields; lines end
	at line breaks only and wrap at 100 characters (NVDA's maximum line length)."""

	def __init__(self, nodes):
		self.parts = []
		self.fields = []
		self.s = ""
		self._add(nodes, 0)

	def _add(self, nodes, depth):
		for n in nodes:
			if isinstance(n, str):
				self.parts.append((len(self.s), len(self.s) + len(n)))
				self.s += n
				continue
			field, kids = n
			f = [len(self.s), None, field, depth]
			self.fields.append(f)
			self._add(kids, depth + 1)
			f[1] = len(self.s)

	def lineOffsets(self, off):
		s = self.s
		off = max(0, min(off, len(s) - 1))
		a = s.rfind('\n', 0, off) + 1
		b = s.find('\n', off)
		b = len(s) if b < 0 else b + 1
		cur = a
		while b - cur > 100:
			cut = s.rfind(' ', cur, cur + 100)
			nxt = cut + 1 if cut > cur else cur + 100
			if off < nxt:
				return cur, nxt
			cur = nxt
		return cur, b

	def withFields(self, a, b):
		out = []
		opened = sorted([f for f in self.fields if f[0] <= a < f[1]], key=lambda f: f[3])
		out.extend(TI.FieldCommand('controlStart', f[2]) for f in opened)
		stack = list(opened)
		ev = []
		for f in self.fields:
			if a < f[0] < b:
				ev.append((f[0], 1, f[3], f))
			if a < f[1] <= b and (f in opened or a < f[0]):
				ev.append((f[1], 0, -f[3], f))
		for s0, e0 in self.parts:
			lo, hi = max(a, s0), min(b, e0)
			if lo < hi:
				ev.append((lo, 2, 0, (lo, hi)))
		for _p, kind, _d, f in sorted(ev, key=lambda e: (e[0], e[1], e[2])):
			if kind == 1:
				out.append(TI.FieldCommand('controlStart', f[2])); stack.append(f)
			elif kind == 0:
				if f in stack:
					stack.remove(f); out.append(TI.FieldCommand('controlEnd', None))
			else:
				out.append(TI.FieldCommand('formatChange', TI.FormatField()))
				out.append(self.s[f[0]:f[1]])
		out.extend(TI.FieldCommand('controlEnd', None) for _f in stack)
		return out


def rawLine(self, off):
	return self.story.lineOffsets(off)


def rawWord(self, off):
	a, b = self._getLineOffsets(off)
	for m in re.finditer(r'[^\s]+[ \t\xa0]*|\s', self.story.s[a:b]):
		if m.start() + a <= off < m.end() + a:
			return m.start() + a, m.end() + a
	return off, off + 1


VB.VirtualBufferTextInfo._getLineOffsets = rawLine
VB.VirtualBufferTextInfo._getWordOffsets = rawWord


class VTI(VB.VirtualBufferTextInfo):
	encoding = 'utf_16_le'

	def __init__(self, story, a, b=None):
		self.story = story
		self._startOffset = a
		self._endOffset = a if b is None else b
		self.obj = types.SimpleNamespace(windowHandle=1, name='doc.pdf', rootNVDAObject=None)

	def copy(self):
		return VTI(self.story, self._startOffset, self._endOffset)

	@property
	def text(self):
		return self.story.s[self._startOffset:self._endOffset]

	def _getStoryLength(self):
		return len(self.story.s)

	def _getTextRange(self, a, b):
		return self.story.s[a:b]

	def getTextWithFields(self, fc=None):
		return self.story.withFields(self._startOffset, self._endOffset)

	def expand(self, unit):
		o = self._startOffset
		if unit == TI.UNIT_CHARACTER:
			self._endOffset = o + 1
		elif unit == TI.UNIT_WORD:
			self._startOffset, self._endOffset = self._getWordOffsets(o)
		else:
			self._startOffset, self._endOffset = self._getLineOffsets(o)

	def collapse(self, end=False):
		if end:
			self._startOffset = self._endOffset
		else:
			self._endOffset = self._startOffset

	def move(self, unit, n, endPoint=None):
		o = self._startOffset
		done = 0
		while n > 0 and done < n:
			a, b = self._getLineOffsets(o)
			if b >= len(self.story.s):
				break
			o = b
			done += 1
		while n < 0 and done > n:
			a, b = self._getLineOffsets(o)
			if a <= 0:
				break
			o = self._getLineOffsets(a - 1)[0]
			done -= 1
		self._startOffset = self._endOffset = o
		return done

	def compareEndPoints(self, other, which):
		x = self._startOffset if which.startswith('start') else self._endOffset
		y = other._startOffset if which.endswith('Start') else other._endOffset
		return (x > y) - (x < y)

	def setEndPoint(self, other, which):
		v = other._startOffset if which.endswith('Start') else other._endOffset
		if which.startswith('start'):
			self._startOffset = v
			self._endOffset = max(self._endOffset, v)
		else:
			self._endOffset = v
			self._startOffset = min(self._startOffset, v)


import nepaliReader as NR
from nepaliReader import pdfText, neLexicon, devanagariRepair as D
p = NR.GlobalPlugin()
for _ in range(200):
	if neLexicon.isLoaded():
		break
	time.sleep(0.1)
bad = 0


def check(name, got, want):
	global bad
	ok = got == want
	bad += not ok
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))


# the document as the PDF has it: lines of the page (lineStart), the viewer's text (key) and,
# where it differs, the real text
page = [
	["गोरखा", "नगरपालिकाको", "स्थानीय", "पाठ्यक्रम"],
	["२०७८"],
	["आधारभूत", "तह", "(कक्षा", "४–८)"],
	["शिक्षा,", "युवा", "तथा", "खेलकुद", "शाखा"],
	["नगर", "प्रमुखको", ("सन्देश", "सन्देि")],
	["राज्यको", "संघीय", "संरचनामा"],
	["विपद्"],
	["बुलेटिन", "जारी"],
]
idx = pdfText.DocIndex()
pos = 0
B = []
for line in page:
	for k, w in enumerate(line):
		real, shown = w if isinstance(w, tuple) else (None, w)
		key = pdfText.keyOf(shown)
		idx.starts.append(pos)
		idx.lineStart.append(k == 0)
		idx.words.append((real, None, None, key))
		B.append(pdfText.matchKey(shown))
		pos += len(key)
idx.B = "".join(B)
idx._buildF()
p._isPdfWindow = lambda o: True
p._readyIndex = lambda o: idx
p._pdfIndex = lambda o: idx

R = lambda **kw: TI.ControlField(**kw)
story = Story([
	(R(role='landmark', landmark='region', name='Page 1'), [
		(R(role='heading', level=2), ["गोरखा नगरपालिकाको स्थानीय पाठ\n्\nयक्रम\n"]),
		(R(role='paragraph'), ["२०७८\nआधारभत\nू तह (कक्षा ४–८)\n"]),
		(R(role='paragraph'), ["शिक्षा, युवा तथा खेलकुद शाखा"]),
	]),
	(R(role='landmark', landmark='region', name='Page 2'), [
		(R(role='heading', level=2), ["नगर प्रमख\nु\nको सन्दिे \n"]),
		(R(role='paragraph'), ["राज्यको संघीय संरचनामा\n"]),
		(R(role='paragraph'), ["विपद\n्\nबुलेटिन जारी\n"]),
	]),
])
S = story.s


def lineAt(text):
	o = S.index(text)
	info = VTI(story, o)
	info.expand(TI.UNIT_LINE)
	return info


def spoken(info, unit=TI.UNIT_LINE):
	return "".join(f for f in p._convertFields(info, {}, unit=unit) if isinstance(f, str))


# the rules
check('a line beginning with a sign goes on the line before', NR._sameLine(idx, "", "आधारभत\n", "ू तह (कक्षा ४–८)\n"), True)
check('ि begins a line of the page (it is drawn before its letter)', NR._sameLine(idx, "", "शाखा\n", "िशक्षा\n"), False)
check('after a lone sign: the rest of the word', NR._sameLine(idx, "गोरखा नगरपालिकाको स्थानीय पाठ\n", "्\n", "यक्रम\n"), True)
check('after a lone sign: the next line of the page stays apart', NR._sameLine(idx, "विपद\n", "्\n", "बुलेटिन जारी\n"), False)
check('ordinary lines stay apart', NR._sameLine(idx, "", "२०७८\n", "आधारभत\n"), False)
check('continuesLine: inside a word', idx.continuesLine("नगर प्रमख", "को सन्दिे"), True)
check('continuesLine: the next line of the page', idx.continuesLine("विपद", "बुलेटिन"), False)
check('joined text', NR._joinBrokenLines(idx, "पाठ\n्\nयक्रम\n"), "पाठ्यक्रम\n")

# lines
h = lineAt("गोरखा")
check('heading broken by the viewer is one line', h.text, "गोरखा नगरपालिकाको स्थानीय पाठ\n्\nयक्रम\n")
check('the same line from its middle piece', lineAt("्\nयक्रम").text, h.text)
check('the same line from its last piece', lineAt("यक्रम").text, h.text)
check('heading read once, whole', spoken(h), "गोरखा नगरपालिकाको स्थानीय पाठ्यक्रम\n")
a = lineAt("आधारभत")
check('a sign the viewer moved to the next line', (a.text, spoken(a)), ("आधारभत\nू तह (कक्षा ४–८)\n", "आधारभूत तह (कक्षा ४–८)\n"))
last = lineAt("शिक्षा,")
check('the last line of a page ends where the next page begins', last.text, "शिक्षा, युवा तथा खेलकुद शाखा")
h2 = lineAt("नगर प्रमख")
check('the next page\'s heading is a line of its own', (h2.text, spoken(h2)), ("नगर प्रमख\nु\nको सन्दिे \n", "नगर प्रमुखको सन्देश \n"))
v = lineAt("विपद")
check('a final sign joins its word, the next line of the page stays apart', v.text, "विपद\n्\n")
check('the next line of the page', lineAt("बुलेटिन").text, "बुलेटिन जारी\n")

# moving by line goes over the whole heading
cur = VTI(story, 0)
cur.expand(TI.UNIT_LINE)
seen = []
for _k in range(12):
	seen.append(cur.text)
	nxt = cur.copy()
	nxt.collapse(end=True)
	if nxt._startOffset >= len(S):
		break
	nxt.expand(TI.UNIT_LINE)
	cur = nxt
check('Down Arrow line by line', seen, ["गोरखा नगरपालिकाको स्थानीय पाठ\n्\nयक्रम\n", "२०७८\n", "आधारभत\nू तह (कक्षा ४–८)\n",
	"शिक्षा, युवा तथा खेलकुद शाखा", "नगर प्रमख\nु\nको सन्दिे \n", "राज्यको संघीय संरचनामा\n", "विपद\n्\n", "बुलेटिन जारी\n"])

# words: a word the viewer broke over lines is one word
w = VTI(story, S.index("पाठ\n"))
w.expand(TI.UNIT_WORD)
check('word broken over lines', (w.text, spoken(w, TI.UNIT_WORD)), ("पाठ\n्\nयक्रम", "पाठ्यक्रम"))
w = VTI(story, S.index("प्रमख"))
w.expand(TI.UNIT_WORD)
check('word with a sign the viewer put after its letter', spoken(w, TI.UNIT_WORD).strip(), "प्रमुखको")

# file names shown as mojibake, with bytes lost as "_" (read as Latin-1), and file URLs
title = "à¤¸à¥_à¤¥à¤¾à¤¨à¥_à¤¯ à¤ªà¤¾à¤\u00a0à¥_à¤¯à¤_à¥_à¤°à¤® 2078.pdf"
check('mojibake with lost bytes', D.decodeMojibake(title), "स्थानीय पाठ्यक्रम 2078.pdf")
D.docWords = None
check('an ambiguous word is left as it is', D.decodeMojibake("à¤_à¥_à¤°à¤_à¤¾"), "à¤_à¥_à¤°à¤_à¤¾")
D.docWords = lambda: {"गोरखा"}
check('the document\'s own word settles it', D.decodeMojibake("à¤_à¥_à¤°à¤_à¤¾"), "गोरखा")
D.docWords = p._docWordSet
url = "file:///C:/Users/Suyog/Downloads/%C3%A0%C2%A4%C2%B8%C3%A0%C2%A5_%C3%A0%C2%A4%C2%A5%C3%A0%C2%A4%C2%BE%C3%A0%C2%A4%C2%A8%C3%A0%C2%A5_%C3%A0%C2%A4%C2%AF%202078.pdf"
check('a file URL read as its name', D.decodeUrlName(url), "file:///C:/Users/Suyog/Downloads/स्थानीय 2078.pdf")
check('an English URL is left as it is', D.decodeUrlName("https://example.com/a%20b.pdf"), "https://example.com/a%20b.pdf")
check('a URL is never read as Preeti', p._filterSpeechSequence(["https://ndrrma.gov.np/en/situation-report/464"]),
	["https://ndrrma.gov.np/en/situation-report/464"])
check('a file URL in speech', [x for x in p._filterSpeechSequence([url]) if isinstance(x, str)],
	["file:///C:/Users/Suyog/Downloads/स्थानीय 2078.pdf"])

print("FAILED" if bad else "ALL OK", bad)
sys.exit(1 if bad else 0)
