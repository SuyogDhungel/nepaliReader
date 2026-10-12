# PDF tables: cells from drawn borders or tags, merged cells, copy as a table (tabs + HTML),
# the accessible view, and lines where the viewer glued its own words to the page's text.
import sys, time
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
import nepaliReader as NR
from nepaliReader import pdfLayout as L, pdfReader, neLexicon
p = NR.GlobalPlugin()
for _ in range(100):
	if neLexicon.isLoaded():
		break
	time.sleep(0.1)
bad = 0


def check(name, got, want):
	global bad
	ok = got == want
	bad += not ok
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))


# drawing operators are read only when asked for
ops = list(pdfReader.contentOps(b"q 2 0 0 2 0 0 cm 0 0 50 0.5 re f BT (a re b) Tj ET Q", graphics=True))
check('graphics ops', [o for o, a in ops], ['q', 'cm', 're', 'f', 'BT', 'Tj', 'ET', 'Q'])
check('no graphics ops by default', [o for o, a in pdfReader.contentOps(b"0 0 50 0.5 re f BT (x) Tj ET")], ['BT', 'Tj', 'ET'])

# a 3 x 3 grid of thin filled rectangles (as Word draws borders); the first column's two lower
# cells are one merged cell (no line between them there)
content = []
for y in (300, 280, 260, 240):
	x1 = 300
	if y == 260:
		content.append("100 %d 200 0.5 re f" % y)  # starts at x=100: column 1 is merged here
	else:
		content.append("0 %d %d 0.5 re f" % (y, x1))
for x in (0, 100, 200, 300):
	content.append("%d 240 0.5 60 re f" % x)
hs, vs = L.rulings(pdfReader.Document(b"%PDF-1.4\n"), " ".join(content).encode(), {})
tables = L.gridTables(hs, vs)
check('one table', len(tables), 1)
t = tables[0]
check('rows x cols', (t['nr'], t['nc']), (3, 3))
merged = [c for c in t['cells'] if c[6] == 2]
check('merged cell spans two rows', [(c[4], c[5], c[6], c[7]) for c in merged], [(1, 0, 2, 1)])

# tagged cells: a cell spanning two rows takes its column in the next row
rows = [[{'rs': 2, 'cs': 1}, {'rs': 1, 'cs': 1}], [{'rs': 1, 'cs': 1}]]
check('tagged grid', L._gridOfRows(rows), [(0, 0, 0), (0, 1, 1), (1, 0, 1)])


# copy as a table
class Idx:
	pass


idx = Idx()
idx.words = [(w, None, None, w) for w in ['घटना', 'जिल्ला', 'सर्पदंश', 'सिरहा', 'सोलु', 'खुम्बु', 'पछिको', 'वाक्य']]
idx.lineStart = [True, False, True, False, True, False, True, False]
idx.layout = {'tables': [{'p': 0, 'nr': 3, 'nc': 2, 'cells': [
	[0, 0, 1, 1, 1, [0]], [0, 1, 1, 1, 1, [1]], [1, 0, 2, 1, 0, [2]], [1, 1, 1, 1, 0, [3]], [2, 1, 1, 1, 0, [4, 5]]]}],
	'blocks': None, 'heads': {}, 'wpage': [0] * 8}
clip = L.clipLines(idx, [('घटना जिल्ला', [0, 1]), ('सर्पदंश सिरहा', [2, 3]), ('सोलु खुम्बु', [4, 5]), ('पछिको वाक्य', [6, 7])])
check('copy: tab separated rows', clip[0], 'घटना\tजिल्ला\r\nसर्पदंश\tसिरहा\r\n\tसोलु खुम्बु\r\nपछिको वाक्य')
check('copy: html table', clip[1], '<table><tr><th>घटना</th><th>जिल्ला</th></tr><tr><td rowspan="2">सर्पदंश</td><td>सिरहा</td></tr>'
	'<tr><td>सोलु खुम्बु</td></tr></table><p>पछिको वाक्य</p>')
check('copy: one cell stays plain', L.clipLines(idx, [('सोलु खुम्बु', [4, 5])]), None)
check('copy: the viewer\'s own line stays', L.clipLines(idx, [('Toggle sidebar', []), ('घटना जिल्ला', [0, 1])])[0], 'Toggle sidebar\r\nघटना\tजिल्ला')
html = L.documentHtml(idx, 'test')
check('view has the table', '<td rowspan="2">सर्पदंश</td>' in html and '<p>पछिको वाक्य</p>' in html, True)
check('view has page regions', '<section aria-label="Page 1">' in html, True)
data = L.cfHtml('<b>क</b>')
head = data.split(b'<html>')[0].decode()
vals = dict(l.split(':', 1) for l in head.split('\r\n') if ':' in l)
check('clipboard html offsets', data[int(vals['StartFragment']):int(vals['EndFragment'])].decode('utf-8'), '<b>क</b>')


# a line where Chrome glued its own words to the page text: the Devanagari part is looked up
class FakeIdx:
	B = ''
	def lookup(self, text):
		return [('पहिरो', True)] if text == 'पटहरो' else None
	def knows(self, w):
		return False
	def spanAt(self, *a):
		return None


got = p._indexText(None, FakeIdx(), 'ImageImageC:\\Users\\a\\x.PNGUnlabeled graphicपटहरो')
check('glued viewer label', got, 'ImageImageC:\\Users\\a\\x.PNGUnlabeled graphicपहिरो')
check('digits of a file name are not looked up', p._indexText(None, FakeIdx(), 'Toggle sidebar२०८३-०६-२६.pdf'), None)

print('FAILED' if bad else 'ALL OK', bad)
sys.exit(1 if bad else 0)
