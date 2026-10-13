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

# reading in place: NVDA's own table cell and heading fields around the words they hold
import textInfos as TI
FC = TI.FieldCommand
idx.layout['heads'] = {7: 1}
idx.layout['blocks'] = [0, 0, 0, 0, 0, 0, 7, 7]
L._layoutCache(idx)
check('cell attrs', L.cellAttrs(idx, 0, 3)[1], {'role': 'cell', 'table-id': L.TABLE_ID_BASE, 'table-rownumber': 2, 'table-columnnumber': 2,
	'table-rowsspanned': 1, 'table-columnsspanned': 1, 'table-columnheadertext': 'जिल्ला'})
check('header cell role', L.cellAttrs(idx, 0, 0)[1]['role'], 'columnheader')
check('table attrs', L.cellAttrs(idx, 0, 4)[0], {'role': 'table', 'table-id': L.TABLE_ID_BASE, 'table-rowcount': 3, 'table-columncount': 2})
idx.locate = lambda *a, **k: None  # (not found exactly: the lines are looked up as reading looks them up)
p._isPdfWindow = lambda obj: True
p._readyIndex = lambda obj: idx
lineIds = {'line2': [2, 3], 'line3': [4, 5], 'line4': [6, 7]}
def fakeIndexText(info, ix, text):
	ix.touched.extend(lineIds[text])
	return text
p._indexText = fakeIndexText
class LineInfo:
	def __init__(s, text, fields): s.text = text; s.obj = None; s._f = fields
	def getTextWithFields(s, fc=None): return list(s._f)
def shape(fields):
	out = []
	for f in fields:
		if isinstance(f, FC):
			out.append((f.command, dict(f.field or {}).get('role'), dict(f.field or {}).get('table-columnnumber') or dict(f.field or {}).get('level')))
		else:
			out.append(f)
	return out
para = TI.ControlField(role='paragraph')
got = p._withLayout(LineInfo('line2', []), [FC('controlStart', para), FC('formatChange', TI.FormatField()), 'सर्पदंश सिरहा', FC('controlEnd', None)])
check('two cells on one line (the table outside the viewer\'s paragraph)', shape(got), [('controlStart', 'table', None), ('controlStart', 'paragraph', None), ('formatChange', None, None), ('controlStart', 'cell', 1),
	'सर्पदंश ', ('controlEnd', None, None), ('controlStart', 'cell', 2), 'सिरहा', ('controlEnd', None, None), ('controlEnd', None, None), ('controlEnd', None, None)])
got = p._withLayout(LineInfo('line4', []), [FC('controlStart', para), 'पछिको वाक्य', FC('controlEnd', None)])
check('heading line', shape(got), [('controlStart', 'paragraph', None), ('controlStart', 'heading', 1), 'पछिको वाक्य', ('controlEnd', None, None), ('controlEnd', None, None)])
got = p._withLayout(LineInfo('line2', []), [FC('controlStart', para), 'सर्पदंश ', FC('controlStart', TI.ControlField(role='link')), 'सिरहा', FC('controlEnd', None), FC('controlEnd', None)])
check('a cell that starts where a link starts', shape(got), [('controlStart', 'table', None), ('controlStart', 'paragraph', None), ('controlStart', 'cell', 1), 'सर्पदंश ',
	('controlEnd', None, None), ('controlStart', 'cell', 2), ('controlStart', 'link', None), 'सिरहा', ('controlEnd', None, None), ('controlEnd', None, None), ('controlEnd', None, None), ('controlEnd', None, None)])
crossed = [FC('controlStart', para), 'सर्पदंश ', FC('controlEnd', None), FC('controlStart', para), 'सिरहा', FC('controlEnd', None)]
check('fields that do not nest are left alone', p._withLayout(LineInfo('line2', []), crossed), crossed)
already = [FC('controlStart', TI.ControlField(role='heading', level=2)), 'पछिको वाक्य', FC('controlEnd', None)]
check('the viewer\'s own heading is kept', p._withLayout(LineInfo('line4', []), already), already)
# a line that occurs in several rows is placed by the lines around it
from nepaliReader import pdfText as PT
ws = ['सोलुखुम्बु', 'सर्पले', '०', '१', 'लागि', 'नवलपरासी', 'माछा', '०', '१', 'लागि']
keys = [w for w in ws]
starts = []
pos = 0
for k in keys:
	starts.append(pos)
	pos += len(k)
D = PT.DocIndex.restore({'v': PT.INDEX_VERSION, 'B': ''.join(keys), 'starts': starts, 'words': [(w, None, None, w) for w in ws],
	'lineStart': [True] * len(ws), 'fixed': 0, 'stats': {}, 'layout': None})
check('repeated line: first row', D.locate('० १ लागि', lambda: 'सोलुखुम्बु सर्पले', lambda: 'नवलपरासी'), [2, 3, 4])
check('repeated line: second row', D.locate('० १ लागि', lambda: 'नवलपरासी माछा', lambda: ''), [7, 8, 9])
check('a word of the line', D.locate('० १ लागि', lambda: 'नवलपरासी माछा', lambda: '', part=(2, 1)), [8])
check('a space belongs to the next word', D.locate('० १ लागि', lambda: 'सोलुखुम्बु सर्पले', lambda: '', part=(1, 1)), [3])
# bold / italic / underline as the page draws them, merged into the viewer's own format
def fshape(fields):
	return [(f.command, {k: v for k, v in (f.field or {}).items()}) if isinstance(f, FC) else f for f in fields]
got = NR._applyStyles([FC('formatChange', TI.FormatField({'font-name': 'Kalimati'})), 'घटना सारांशः महाकुलुङ'], [(0, 5), (12, 0)])
check('drawn bold and underline', fshape(got), [('formatChange', {'font-name': 'Kalimati', 'bold': True, 'underline': True}), 'घटना सारांशः',
	('formatChange', {'font-name': 'Kalimati'}), ' महाकुलुङ'])
got = NR._applyStyles([FC('formatChange', TI.FormatField({'bold': True})), 'क ख'], [(0, 0)])
check('the viewer\'s bold stays', fshape(got), [('formatChange', {'bold': True}), 'क ख'])
got = NR._applyStyles(['क ', FC('formatChange', TI.FormatField({'font-name': 'X'})), 'ख'], [(0, 2), (2, 0)])
check('italic before a viewer format change', fshape(got), [('formatChange', {'italic': True}), 'क ', ('formatChange', {'font-name': 'X'}), 'ख'])
got = NR._applyStyles([FC('formatChange', TI.FormatField()), 'बालबालिकाको अहित'], [(0, (0, ('justify', 0.0, 36.0)))])
check('paragraph alignment and first line indent', fshape(got), [('formatChange', {'text-align': 'justify', 'first-line-indent': '1.27 cm'}), 'बालबालिकाको अहित'])
got = NR._applyStyles([FC('formatChange', TI.FormatField()), 'परिच्छेद – १ प्रारम्भिक'], [(0, (1, ('center', 0.0, 0.0))), (12, (0, None))])
check('a centred bold title, then plain text', fshape(got), [('formatChange', {'bold': True, 'text-align': 'center'}), 'परिच्छेद – १',
	('formatChange', {}), ' प्रारम्भिक'])
# NVDA's table keys and quick navigation in the viewer, for the PDF's own tables
import collections
# fake NVDA modules for browse mode table navigation
import dataclasses
@dataclasses.dataclass
class TC:  # (NVDA's _TableCell is a dataclass)
	tableID: int
	row: int
	col: int
	rowSpan: int = 1
	colSpan: int = 1
F.mod('documentBase', _TableCell=TC)
class VirtualBuffer:
    def _getTableCellCoords(self, info): raise LookupError
    def _getTableDimensions(self, info): raise LookupError
    def _getTableCellAt(self, tableID, startPos, row, column): raise LookupError
    def _getNearestTableCell(self, startPos, cell, movement, axis): raise LookupError
    def _iterNodesByType(self, itemType, direction='next', pos=None): return iter(())
vb = F.mod('virtualBuffers', VirtualBuffer=VirtualBuffer); vb.__path__=[]
class QNItem:
	def __init__(self, itemType, document, textInfo):
		self.itemType = itemType; self.document = document; self.textInfo = textInfo
	@property
	def label(self):
		return self.textInfo.text
F.mod('browseMode', TextInfoQuickNavItem=QNItem)
class Offsets:
    def __init__(s, a, b): s.startOffset=a; s.endOffset=b
off = F.mod('textInfos.offsets', Offsets=Offsets); TI.offsets = off
TI.POSITION_FIRST='first'; TI.UNIT_LINE='line'
ws2 = ['घटना', 'जिल्ला', 'सर्पदंश', 'सिरहा', 'पछि']
st2 = []
pos = 0
for w in ws2:
	st2.append(pos)
	pos += len(w)
D2 = PT.DocIndex.restore({'v': PT.INDEX_VERSION, 'B': ''.join(ws2), 'starts': st2, 'words': [(w, None, None, w) for w in ws2],
	'lineStart': [True, False, True, False, True], 'fixed': 0, 'stats': {},
	'layout': {'tables': [{'p': 0, 'nr': 2, 'nc': 2, 'cells': [[0, 0, 1, 1, 1, [0]], [0, 1, 1, 1, 1, [1]], [1, 0, 1, 1, 0, [2]], [1, 1, 1, 1, 0, [3]]]}],
		'blocks': [0, 0, 0, 0, 9], 'heads': {9: 2}, 'wpage': [0] * 5}})
story = 'शीर्षक\nघटना जिल्ला\nसर्पदंश सिरहा\nपछि\n'
class TInfo:
    encoding = 'utf_32_le'
    obj = None
    def __init__(s, a, b): s._startOffset=a; s._endOffset=b
    def copy(s): return TInfo(s._startOffset, s._endOffset)
    @property
    def isCollapsed(s): return s._startOffset==s._endOffset
    @property
    def text(s): return story[s._startOffset:s._endOffset]
    def _getStoryLength(s): return len(story)
    def _getTextRange(s, a, b): return story[a:b]
    def collapse(s, end=False):
        if end: s._startOffset=s._endOffset
        else: s._endOffset=s._startOffset
    def expand(s, unit):
        if unit=='line':
            a=story.rfind('\n',0,s._startOffset)+1; b=story.find('\n', s._startOffset); b=len(story) if b<0 else b+1
            s._startOffset, s._endOffset = a, b
        else: s._endOffset=s._startOffset+1
    def setEndPoint(s, o, which):
        if which=='endToStart': s._endOffset=o._startOffset
        elif which=='startToStart': s._startOffset=o._startOffset
        elif which=='endToEnd': s._endOffset=o._endOffset
        elif which=='startToEnd': s._startOffset=o._endOffset
    def compareEndPoints(s, o, which):
        a = s._startOffset if which.startswith('start') else s._endOffset
        b = o._startOffset if which.endswith('Start') else o._endOffset
        return (a > b) - (a < b)
    def move(s, unit, n):
        a=s._startOffset
        if n<0:
            ls=story.rfind('\n',0,a)+1  # NVDA: back to the start of this line when inside it
            if ls < a:
                s._startOffset=s._endOffset=ls; return -1
            b=story.rfind('\n',0,a)  # end of previous line
            if b<0: return 0
            a2=story.rfind('\n',0,b)+1; s._startOffset=s._endOffset=a2; return -1
        b=story.find('\n',a)
        if b<0: return 0
        s._startOffset=s._endOffset=b+1; return 1
class Doc(vb.VirtualBuffer):
    rootNVDAObject=object()
    def makeTextInfo(s, pos):
        if isinstance(pos, Offsets): return TInfo(pos.startOffset, pos.endOffset)
        return TInfo(0,0)
p._patched2 = []
p._patchTableNavigation()
p._isPdfWindow = lambda o: True
p._readyIndex = lambda o: D2
doc = Doc()
cell = doc._getTableCellCoords(TInfo(story.find('सिरहा'), story.find('सिरहा')))
check('caret cell', (cell.row, cell.col, cell.rowSpan, cell.colSpan), (2, 2, 1, 1))
up = doc._getNearestTableCell(TInfo(story.find('सिरहा'), story.find('सिरहा')), cell, 'previous', 'row')
check('previous row', up.text, 'जिल्ला')
left = doc._getNearestTableCell(TInfo(story.find('सिरहा'), story.find('सिरहा')), cell, 'previous', 'column')
check('previous column', left.text, 'सर्पदंश')
check('table size', doc._getTableDimensions(TInfo(story.find('घटना'), story.find('घटना'))), (2, 2))
check('next table', [i.textInfo.text for i in doc._iterNodesByType('table', 'next', TInfo(0, 0))], ['घटना'])
check('next heading', [i.textInfo.text for i in doc._iterNodesByType('heading', 'next', TInfo(0, 0))], ['पछि\n'])
try:
	doc._getNearestTableCell(TInfo(0, 0), cell, 'next', 'column')
	check('edge of table', 'no error', 'LookupError')
except LookupError:
	check('edge of table', 'LookupError', 'LookupError')
# a web table's cell (not the PDF's) goes to NVDA's own code untouched, whatever the cell's type
try:
	doc._getNearestTableCell(TInfo(0, 0), TC(77, 1, 1), 'next', 'column')
	check('web table cell to NVDA', 'returned', 'LookupError from NVDA')
except LookupError:
	check('web table cell to NVDA', 'LookupError from NVDA', 'LookupError from NVDA')
except Exception as e:
	check('web table cell to NVDA', repr(e), 'LookupError from NVDA')
class GI:
	pass
gi = GI()
gi.words = [(w, None, None, w) for w in ['सिरहा', '१५', '५', 'जम्मा', '१२३', '२३']]
check('a number is not split across cells', L.groupOffsets('सिरहा १५ ५', gi, [(1, [0]), (2, [1]), (3, [2])]), [0, 6, 9])
check('a number is not split across cells 2', L.groupOffsets('जम्मा १२३ २३', gi, [(1, [3]), (2, [4]), (3, [5])]), [0, 6, 10])
# a lone "०" deep in a document: whole words only, placed by its neighbours
ws3 = []
for k in range(120):
	ws3 += ['२०८३', 'ला', '०', 'मा']
ws3 += ['नया', '०', 'पुरा']
target = len(ws3) - 2
ws3 += ['ला', '०', 'मा']
st3 = []
pos = 0
for w in ws3:
	st3.append(pos)
	pos += len(w)
D3 = PT.DocIndex.restore({'v': PT.INDEX_VERSION, 'B': ''.join(ws3), 'starts': st3, 'words': [(w, None, None, w) for w in ws3],
	'lineStart': [True] * len(ws3), 'fixed': 0, 'stats': {}, 'layout': None})
check('a lone digit line deep in the document', D3.locate('०', lambda: 'नया', lambda: 'पुरा'), [target])
# a cell that starts mid-line (Chrome keeps a table row on one line): its row is its own
ws4 = ['क', '५', 'ख', 'ग', '५', 'घ']
st4 = []
pos = 0
for w in ws4:
	st4.append(pos)
	pos += len(w)
D4 = PT.DocIndex.restore({'v': PT.INDEX_VERSION, 'B': ''.join(ws4), 'starts': st4, 'words': [(w, None, None, w) for w in ws4],
	'lineStart': [True, False, False, True, False, False], 'fixed': 0, 'stats': {},
	'layout': {'tables': [{'p': 0, 'nr': 2, 'nc': 3, 'cells': [[r, c, 1, 1, 0, [r * 3 + c]] for r in range(2) for c in range(3)]}],
		'blocks': None, 'heads': {}, 'wpage': [0] * 6}})
story = 'क ५ ख\nग ५ घ\n'
p._readyIndex = lambda o: D4
D4._hint = 0
five = story.rfind('५')
got = p._withLayout(TInfo(five, five + 1), [FC('formatChange', TI.FormatField()), '५'])
rows = [f.field.get('table-rownumber') for f in got if isinstance(f, FC) and f.command == 'controlStart' and f.field.get('table-rownumber')]
check('cell in the middle of a line: its own row', rows, [2])
got = p._withLayout(TInfo(five, five + 1), [FC('formatChange', TI.FormatField()), '५'], 'character')
rows = [f.field.get('table-rownumber') for f in got if isinstance(f, FC) and f.command == 'controlStart' and f.field.get('table-rownumber')]
check('a character keeps its cell (no "out of table")', rows, [2])
print('FAILED' if bad else 'ALL OK', bad)
sys.exit(1 if bad else 0)
