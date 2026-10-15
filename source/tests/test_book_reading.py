# Test for book PDF reading order and Devanagari font CMap repairs
import sys, os, time
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')

from nepaliReader import pdfText, neLexicon, detector, pdfReader

bad = 0
def check(name, got, want):
    global bad
    ok = got == want
    bad += not ok
    print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f'\n     got  {got!r}\n     want {want!r}'))

# What the viewer shows for a glyph (the PDF's ToUnicode) is never changed: the index looks up
# exactly that text (Chrome's "लिक्षा" for शिक्षा in a Kokila PDF from Word); the real letters come
# from the glyphs themselves, not from guessing at the text table
class MockFont:
    def __init__(self):
        self.cid = True
        self.program = None
        self.used = {97, 101, 108, 170, 229, 49, 51}
        self.baseFont = "BCDEEE+Kokila"
        self.widths = {170: 0.0, 229: 203.0, 108: 203.0, 97: 543.0, 101: 521.0}
        self.toUnicode = {
            108: 'ल', 97: 'ि', 101: 'ि',
            49: '\u0941\u0901', 51: '\u093f\u0903',
            170: 'ा', 229: 'र'
        }
        self.truth = {}
        self.weak = set()
        self.cidToGid = None
        self.gidOf = {}

f = MockFont()
shown = dict(f.toUnicode)
pdfText.PdfFont.resolveGlyphs(f)
check("the viewer's text of each glyph is kept", f.toUnicode, shown)
check("no letters guessed without the glyphs", f.truth, {})

# Test out-of-order horizontal chunk sorting on the same line
# Simulate line 8 of Page 4:
# Chunk 1 (middle): 'भित्र विद्या' at x=185
# Chunk 2 (left): 'नगरपालिकाले आफ्नो नगर क्षेत्र' at x=72
# Chunk 3 (right): 'लय शिक्षामा' at x=226
class MockFontGlyph:
    baseFont = "BCDEEE+Kokila"
    cid = True
    def text(self, c):
        return c

fg = MockFontGlyph()
def make_glyph(ch, u, v=564.5, size=14.0):
    return (fg, ch, u, v, size, 10.0, None)

# Drawn in drawing order: chunk 1, chunk 2, chunk 3
glyphs = [
    # Chunk 1 at 185
    make_glyph("भि", 185.0), make_glyph("त्र", 195.0),
    make_glyph(" ", 205.0),
    make_glyph("विद्या", 215.0),
    # Chunk 2 at 72
    make_glyph("नगर", 72.0),
    make_glyph(" ", 85.0),
    make_glyph("क्षेत्र", 100.0),
    # Chunk 3 at 226
    make_glyph("लय", 226.0),
    make_glyph(" ", 235.0),
    make_glyph("शिक्षा", 245.0),
]

words = pdfText._words(glyphs, 0)
words_text = ["".join(g[1] for g in w.glyphs) for w in words]
check("Out-of-order horizontal chunks sorted", words_text, ["नगर", "क्षेत्र", "भित्र", "विद्यालय", "शिक्षा"])

print("FAILED" if bad else "ALL OK", bad)
sys.exit(1 if bad else 0)
