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
    def _tableNav(self, movement, axis): pass
    def _tableMovementScriptHelper(self, movement, axis): pass
    def script_moveByLine_forward(self, gesture): pass
    def script_moveByLine_back(self, gesture): pass
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
# single-column table rejected in gridTables
hs_1col = [(0, 300, 100), (0, 200, 100), (0, 100, 100)]
vs_1col = [(0, 100, 300), (100, 100, 300)]
tables_1col = L.gridTables(hs_1col, vs_1col)
check('single-column grid rejected', len(tables_1col), 0)

# 1-row, 2-col table accepted in gridTables
hs_1row = [(200, 0, 200), (100, 0, 200)]
vs_1row = [(0, 100, 200), (100, 100, 200), (200, 100, 200)]
tables_1row = L.gridTables(hs_1row, vs_1row)
check('1-row multi-col grid accepted', len(tables_1row), 1)
check('1-row multi-col dimensions', (tables_1row[0]['nr'], tables_1row[0]['nc']), (1, 2))

# Viewer table with border=0 (table-layout: 1) and 2 columns: table-layout stripped
tbl_fields = [
    FC('controlStart', TI.ControlField(role='table', **{'table-id': 10, 'table-rowcount': 2, 'table-columncount': 2, 'table-layout': '1'})),
    FC('controlStart', TI.ControlField(role='cell', **{'table-id': 10, 'table-rownumber': 1, 'table-columnnumber': 1, 'table-layout': '1'})),
    'युद्ध',
    FC('controlEnd', None),
    FC('controlEnd', None)
]
filtered = p._filterPdfViewerTableFields(LineInfo('test', []), tbl_fields)
check('border-0 multi-col table removes layout flag', [f.field.get('table-layout') for f in filtered if isinstance(f, FC) and f.command == 'controlStart'], [None, None])
check('border-0 multi-col preserves table role', [f.field.get('role') for f in filtered if isinstance(f, FC) and f.command == 'controlStart'], ['table', 'cell'])

# Viewer table with 1 column (e.g. 6 rows 1 column cards): table and cell fields stripped
card_fields = [
    FC('controlStart', TI.ControlField(role='table', **{'table-id': 20, 'table-rowcount': 6, 'table-columncount': 1})),
    FC('controlStart', TI.ControlField(role='cell', **{'table-id': 20, 'table-rownumber': 1, 'table-columnnumber': 1})),
    'कार्ड १',
    FC('controlEnd', None),
    FC('controlEnd', None)
]
filtered_cards = p._filterPdfViewerTableFields(LineInfo('test', []), card_fields)
check('single-column table fields stripped', [f for f in filtered_cards if isinstance(f, FC)], [])
check('single-column table text kept', ''.join(f for f in filtered_cards if isinstance(f, str)), 'कार्ड १')

# Down arrow line offset splitting: chronologically cell-by-cell
import types
tinfo = TInfo(0, len('क ५ ख'))
tinfo.obj = types.SimpleNamespace(rootNVDAObject=object())
offsets0 = p._pdfCellLineOffsets(tinfo, 0, (0, len('क ५ ख')))
check('line offset for cell 0', offsets0, (0, 2))
offsets1 = p._pdfCellLineOffsets(tinfo, 2, (0, len('क ५ ख')))
check('line offset for cell 1', offsets1, (2, 4))
offsets2 = p._pdfCellLineOffsets(tinfo, 4, (0, len('क ५ ख')))
check('line offset for cell 2', offsets2, (4, 5))

# Multi-line cell table navigation with Ctrl+Alt+Arrows
ml_story = 'शीर्षक\nपहिलो लाइन दोस्रो लाइन\n'
story = ml_story
spoken_nav = []
F.sp.speakTextInfo = lambda info, *a, **k: spoken_nav.append(info.text)
doc._getNearestTableCell = lambda info, cell, movement, axis: TInfo(7, len(ml_story) - 1)
doc.selection = TInfo(0, 0)
doc._getTableCellCoords = lambda info: TC(L.TABLE_ID_BASE, 1, 1)
doc._tableNav('next', 'column')
check('tableNav speaks full cell across lines', spoken_nav[-1], 'पहिलो लाइन दोस्रो लाइन')

# Chronological Down Arrow navigation in a table (cell-by-cell)
tbl_cells = {
	(1, 1): TInfo(0, 5),   # Row 1 Col 1
	(1, 2): TInfo(6, 12),  # Row 1 Col 2
	(2, 1): TInfo(13, 20), # Row 2 Col 1
	(2, 2): TInfo(21, 30), # Row 2 Col 2
}
def mock_getTableCellAt(tid, sPos, r, c):
	if (r, c) in tbl_cells:
		return tbl_cells[(r, c)]
	raise LookupError
doc._getTableCellAt = mock_getTableCellAt
doc._getTableDimensions = lambda info: (2, 2)
def mock_coords(info):
	st = getattr(info, '_startOffset', 0)
	for (r, c), ti in tbl_cells.items():
		if ti._startOffset <= st < ti._endOffset:
			return TC(L.TABLE_ID_BASE, r, c)
	raise LookupError
doc._getTableCellCoords = mock_coords

# Caret at Row 1, Col 1
doc.selection = tbl_cells[(1, 1)].copy()
spoken_down = []
F.sp.speakTextInfo = lambda info, *a, **k: spoken_down.append((info._startOffset, info._endOffset))

# Down Arrow 1: moves to Row 1, Col 2
doc.script_moveByLine_forward(None)
check('down arrow moves to row 1 col 2', spoken_down[-1], (6, 12))

# Down Arrow 2: moves to Row 2, Col 1
doc.script_moveByLine_forward(None)
check('down arrow moves to row 2 col 1', spoken_down[-1], (13, 20))

# Down Arrow 3: moves to Row 2, Col 2
doc.script_moveByLine_forward(None)
check('down arrow moves to row 2 col 2', spoken_down[-1], (21, 30))

# Up Arrow 1: moves back to Row 2, Col 1
doc.script_moveByLine_back(None)
check('up arrow moves back to row 2 col 1', spoken_down[-1], (13, 20))

# Multi-line column navigation test:
# Row 1 Col 1 has 3 lines: 'क १\nक २\nक ३' (0..11)
# Row 1 Col 2 has 1 line: 'ख १' (12..16)
ml_cells = {
	(1, 1): TInfo(0, 11),  # text = 'क १\nक २\nक ३'
	(1, 2): TInfo(12, 16), # text = 'ख १'
}
story = 'क १\nक २\nक ३\nख १\n'
doc._getTableCellAt = lambda tid, sPos, r, c: ml_cells.get((r, c)) or (_ for _ in ()).throw(LookupError)
doc._getTableDimensions = lambda info: (1, 2)
def mock_ml_coords(info):
	st = getattr(info, '_startOffset', 0)
	for (r, c), ti in ml_cells.items():
		if ti._startOffset <= st < ti._endOffset:
			return TC(L.TABLE_ID_BASE, r, c)
	raise LookupError
doc._getTableCellCoords = mock_ml_coords

# Start at Line 1 of Col 1
doc.selection = TInfo(0, 4)
ml_spoken = []
F.sp.speakTextInfo = lambda info, *a, **k: ml_spoken.append(info.text.strip())

# Down Arrow 1: moves to Line 2 of Col 1
doc.script_moveByLine_forward(None)
check('multiline col1 down arrow step 1: line 2', ml_spoken[-1], 'क २')

# Down Arrow 2: moves to Line 3 of Col 1
doc.script_moveByLine_forward(None)
check('multiline col1 down arrow step 2: line 3', ml_spoken[-1], 'क ३')

# Down Arrow 3: moves to Col 2
doc.script_moveByLine_forward(None)
check('multiline col1 down arrow step 3: col 2', ml_spoken[-1], 'ख १')

# Up Arrow 1 from Col 2: moves back to LAST line of Col 1 (Line 3)
doc.script_moveByLine_back(None)
check('multiline up arrow back to last line of col 1', ml_spoken[-1], 'क ३')

# Up Arrow 2: moves to Line 2 of Col 1
doc.script_moveByLine_back(None)
check('multiline up arrow back to line 2 of col 1', ml_spoken[-1], 'क २')

# Up Arrow 3: moves to Line 1 of Col 1
doc.script_moveByLine_back(None)
check('multiline up arrow back to line 1 of col 1', ml_spoken[-1], 'क १')

# Text above table test:
orig_called = []
def fake_orig(s, g):
	orig_called.append(True)
	return True
doc.selection = TInfo(100, 105)
doc._getTableCellCoords = lambda info: (_ for _ in ()).throw(LookupError)
p._handlePdfLineMove(doc, None, 1, fake_orig)
check('text above table calls orig without skipping', len(orig_called) > 0, True)

# Table exit boundaries cleanly calling orig:
# 1. Down Arrow past last cell of table
doc._getTableCellCoords = mock_ml_coords
doc.selection = TInfo(12, 16) # Col 2 (last cell)
orig_down = []
p._handlePdfLineMove(doc, None, 1, lambda s, g: orig_down.append(True))
check('down arrow past last cell cleanly calls orig', len(orig_down) > 0, True)

# 2. Up Arrow before first cell of table
doc.selection = TInfo(0, 4) # Col 1 Line 1 (first line of first cell)
orig_up = []
p._handlePdfLineMove(doc, None, -1, lambda s, g: orig_up.append(True))
check('up arrow before first cell cleanly calls orig', len(orig_up) > 0, True)

# Chrome AI / OCR PDF detection test
class MockOcrDoc:
	def makeTextInfo(self, pos):
		return types.SimpleNamespace(text="This PDF is inaccessible. Text extracted, powered by Google AI\nTable data...", expand=lambda u: None)
mock_ocr = MockOcrDoc()
check('detects Chrome AI extracted PDF', p._isPdfViewerObj(mock_ocr), True)

# Quick Nav thumbnail protection tests:
# 1. When viewer has native headings, running out of headings at pos does NOT synthesize off-screen items
native_heading = QNItem('heading', doc, TInfo(0, 5))
def fake_orig_with_native(obj, itemType, direction, pos):
	if pos is None:
		yield native_heading
	# at pos != None (e.g. end of page), return empty
qn_result = list(p._pdfQuickNav(doc, iter(()), 'heading', 'next', TInfo(10, 10), orig=fake_orig_with_native))
check('native headings present stops synthesis at page boundary', qn_result, [])

# 2. Candidate items matching thumbnail text are blocked
doc_thumb = Doc()
doc_thumb.makeTextInfo = lambda pos: types.SimpleNamespace(text="Page 2 thumbnail", expand=lambda u: None, copy=lambda: types.SimpleNamespace(text="Page 2 thumbnail", collapse=lambda: None))
thumb_qn = list(p._pdfQuickNav(doc_thumb, iter(()), 'heading', 'next', None))
check('thumbnail text is blocked from quick nav', thumb_qn, [])

# Table lookahead entry from text above table:
story = 'शीर्षक\nघटना जिल्ला\nसर्पदंश सिरहा\nपछि\n'
doc_entry = Doc()
g_start = story.find('घटना')
j_start = story.find('जिल्ला')
s_start = story.find('सर्पदंश')
si_start = story.find('सिरहा')
p_start = story.find('पछि')

doc_entry_cells = {
	(1, 1): TInfo(g_start, g_start + len('घटना')),
	(1, 2): TInfo(j_start, j_start + len('जिल्ला')),
	(2, 1): TInfo(s_start, s_start + len('सर्पदंश')),
	(2, 2): TInfo(si_start, si_start + len('सिरहा')),
}
doc_entry._getTableDimensions = lambda info: (2, 2)
def mock_entry_coords(info):
	st = getattr(info, '_startOffset', 0)
	for (r, c), ti in doc_entry_cells.items():
		if ti._startOffset <= st < ti._endOffset:
			return TC(L.TABLE_ID_BASE, r, c)
	raise LookupError
doc_entry._getTableCellCoords = mock_entry_coords
doc_entry._getTableCellAt = lambda tid, sp, r, c: doc_entry_cells.get((r, c)) or (_ for _ in ()).throw(LookupError)

# Caret on line above table: 'शीर्षक'
doc_entry.selection = TInfo(0, 5)
entry_orig_called = []
entry_spoken = []
F.sp.speakTextInfo = lambda info, *a, **k: entry_spoken.append(info.text.strip())
F.spoken.clear()
p._handlePdfLineMove(doc_entry, None, 1, lambda o, g: entry_orig_called.append(True))
check('table entry lookahead Down Arrow does not call orig', len(entry_orig_called), 0)
check('table entry lookahead lands on row 1 col 1', (doc_entry.selection._startOffset, doc_entry.selection._endOffset), (g_start, g_start))
check('table entry lookahead speaks row 1 col 1 cell text', entry_spoken[-1], 'घटना')
check('table entry lookahead speaks table dimensions and coordinates', any('table with 2 rows and 2 columns' in s for s in F.spoken), True)

# Table lookahead entry from text below table:
# Caret on line below table: 'पछि'
doc_entry.selection = TInfo(p_start, p_start + len('पछि'))
entry_up_orig_called = []
entry_up_spoken = []
F.sp.speakTextInfo = lambda info, *a, **k: entry_up_spoken.append(info.text.strip())
p._handlePdfLineMove(doc_entry, None, -1, lambda o, g: entry_up_orig_called.append(True))
check('table entry lookahead Up Arrow does not call orig', len(entry_up_orig_called), 0)
check('table entry lookahead Up Arrow lands on last cell (row 2 col 2)', (doc_entry.selection._startOffset, doc_entry.selection._endOffset), (si_start, si_start))

# Cell containing <h2> heading preserves both heading and table cell structure:
p._readyIndex = lambda o: idx
h2_fields = [FC('controlStart', TI.ControlField(role='heading', level=2)), 'सर्पदंश सिरहा', FC('controlEnd', None)]
h2_got = p._withLayout(LineInfo('line2', []), h2_fields)
check('cell styled as h2 has table role', any(f.command == 'controlStart' and dict(f.field or {}).get('role') == 'table' for f in h2_got if isinstance(f, FC)), True)
check('cell styled as h2 has cell role', any(f.command == 'controlStart' and dict(f.field or {}).get('role') == 'cell' for f in h2_got if isinstance(f, FC)), True)
check('cell styled as h2 preserves heading role', any(f.command == 'controlStart' and dict(f.field or {}).get('role') == 'heading' for f in h2_got if isinstance(f, FC)), True)

# Split / 2-row multi-level table header detection:
# Table with 3 rows, 2 cols:
# Row 0: spanning header 'मुख्य' (1 cell spanning 2 cols, or fewer than nc)
# Row 1: sub-headers 'क', 'ख'
# Row 2: data cells '१', '२'
split_idx = Idx()
split_idx.words = [(w, None, None, w) for w in ['मुख्य', 'क', 'ख', '१', '२']]
split_idx.lineStart = [True, True, False, True, False]
split_idx.layout = {'tables': [{
	'p': 0, 'nr': 3, 'nc': 2, 'cells': [
		[0, 0, 1, 2, 0, [0]], # Row 0, col 0, spans 2 cols: 'मुख्य'
		[1, 0, 1, 1, 0, [1]], # Row 1, col 0: 'क'
		[1, 1, 1, 1, 0, [2]], # Row 1, col 1: 'ख'
		[2, 0, 1, 1, 0, [3]], # Row 2, col 0: '१'
		[2, 1, 1, 1, 0, [4]], # Row 2, col 1: '२'
	]
}], 'blocks': None, 'heads': {}, 'wpage': [0] * 5}
L._layoutCache(split_idx)
split_hrows = L._detectHeaderRows(split_idx.layout['tables'][0], split_idx.layout['tables'][0]['cells'])
check('split header detects row 0 and row 1 as header rows', split_hrows, {0, 1})
_, split_data_cell = L.cellAttrs(split_idx, 0, 3) # cell 3 is row 2 col 0 ('१')
check('split header combines row 0 and row 1 text into column header', split_data_cell.get('table-columnheadertext'), 'मुख्य क')

# announceTableHeaders toggle in settings:
F.conf['nepaliReader']['announceTableHeaders'] = False
got_no_headers = p._withLayout(LineInfo('line2', []), [FC('controlStart', para), 'सर्पदंश सिरहा', FC('controlEnd', None)])
check('announceTableHeaders=False removes column header text', any(dict(f.field or {}).get('table-columnheadertext') for f in got_no_headers if isinstance(f, FC) and f.command == 'controlStart'), False)
F.conf['nepaliReader']['announceTableHeaders'] = True

# Duplicate announcement prevention in _speakTableCell:
test_layout_idx = Idx()
test_layout_idx.words = [('नाम', None, None, 'नाम'), ('थर', None, None, 'थर'), ('रोशन', None, None, 'रोशन'), ('गौतम', None, None, 'गौतम')]
test_layout_idx.lineStart = [True, False, True, False]
test_layout_idx.layout = {'tables': [{
	'p': 0, 'nr': 2, 'nc': 2, 'cells': [
		[0, 0, 1, 1, 0, [0]], # Header cell 'नाम'
		[0, 1, 1, 1, 0, [1]], # Header cell 'थर'
		[1, 0, 1, 1, 0, [2]], # Data cell 'रोशन'
		[1, 1, 1, 1, 0, [3]], # Data cell 'गौतम'
	]
}], 'blocks': None, 'heads': {}, 'wpage': [0, 0, 0, 0]}
L._layoutCache(test_layout_idx)
def mock_locate_layout(text, before, after, part=None, where=None):
	if 'नाम' in text: return [0]
	if 'थर' in text: return [1]
	if 'रोशन' in text: return [2]
	if 'गौतम' in text: return [3]
	return None
test_layout_idx.locate = mock_locate_layout

class TestDoc: pass
class TestCellInfo:
	def __init__(self, text):
		self.text = text
		self.obj = TestDoc()
	def getTextWithFields(self, fc=None):
		return [self.text]

test_cell_info = TestCellInfo('रोशन')
p._readyIndex = lambda o: test_layout_idx
p._isPdfWindow = lambda o: True

check('layout cell hasCoords returns True', p._hasCellCoords(test_cell_info), True)
check('layout cell hasHeader returns True', p._hasColumnHeader(test_cell_info), True)

F.spoken.clear()
p._speakTableCell(test_cell_info.obj, test_cell_info, prevCoord=(1, 1), newCoord=(2, 1), enteredTable=False, tableID=0)
check('cell move with layout does not emit redundant speakMessage', len(F.spoken), 0)

# Fallback when layout is absent:
fallback_info = TestCellInfo('रोशन')
p._readyIndex = lambda o: None
p._isPdfWindow = lambda o: False
F.spoken.clear()
p._speakTableCell(fallback_info.obj, fallback_info, prevCoord=(1, 1), newCoord=(2, 1), enteredTable=False, tableID=0)
check('cell move without layout uses fallback speakMessage', F.spoken, ['row 2'])

# Rejecting tables with N cols in top row and blank / 1-col rest:
# 1. Top row 2 cols, rest blank: rejected in pdfLayout
c_blank_body = [
	[0, 0, 1, 1, 0, [0]], [0, 1, 1, 1, 0, [1]],
	[1, 0, 1, 1, 0, []], [1, 1, 1, 1, 0, []],
	[2, 0, 1, 1, 0, []], [2, 1, 1, 1, 0, []],
]
check('top row multi-col with blank body rows rejected', L._isRealTable(3, 2, c_blank_body), False)

# 2. Top row 2 cols, rest only 1 col (e.g. spanning across): rejected in pdfLayout
c_1col_body = [
	[0, 0, 1, 1, 0, [0]], [0, 1, 1, 1, 0, [1]],
	[1, 0, 1, 2, 0, [2]],
	[2, 0, 1, 2, 0, [3]],
]
check('top row multi-col with 1-col body rows rejected', L._isRealTable(3, 2, c_1col_body), False)

# 3. Top row 2 cols, rest has only col 0 filled (col 1 blank): rejected in pdfLayout
c_partial_1col = [
	[0, 0, 1, 1, 0, [0]], [0, 1, 1, 1, 0, [1]],
	[1, 0, 1, 1, 0, [2]], [1, 1, 1, 1, 0, []],
	[2, 0, 1, 1, 0, [3]], [2, 1, 1, 1, 0, []],
]
check('top row multi-col with only 1 column populated in body rejected', L._isRealTable(3, 2, c_partial_1col), False)

# 4. Real 2x2 table: accepted in pdfLayout
c_real_table = [
	[0, 0, 1, 1, 0, [0]], [0, 1, 1, 1, 0, [1]],
	[1, 0, 1, 1, 0, [2]], [1, 1, 1, 1, 0, [3]],
]
check('real 2x2 table accepted', L._isRealTable(2, 2, c_real_table), True)

# 5. Viewer table with top row 2 cols and body rows blank: stripped in _filterPdfViewerTableFields
class MockViewerTableDoc:
	def __init__(self, cells):
		self.cells = cells
	def _getTableDimensions(self, info):
		return (3, 2)
	def _getTableCellAt(self, tid, sel, r, c):
		if (r, c) in self.cells:
			txt = self.cells[(r, c)]
			return types.SimpleNamespace(text=txt, _startOffset=(r * 100 + c) if txt else None)
		raise LookupError

mock_blank_doc = MockViewerTableDoc({(1, 1): 'शीर्षक', (1, 2): 'मिति', (2, 1): '', (2, 2): '', (3, 1): '', (3, 2): ''})
check('viewer table with blank body rejected by _isViewerTableReal', p._isViewerTableReal(mock_blank_doc, None, 50, 3, 2), False)

mock_1col_doc = MockViewerTableDoc({(1, 1): 'शीर्षक', (1, 2): 'मिति', (2, 1): 'अनुच्छेद १', (2, 2): '', (3, 1): 'अनुच्छेद २', (3, 2): ''})
check('viewer table with 1-col body rejected by _isViewerTableReal', p._isViewerTableReal(mock_1col_doc, None, 50, 3, 2), False)

mock_real_doc = MockViewerTableDoc({(1, 1): 'नाम', (1, 2): 'थर', (2, 1): 'रोशन', (2, 2): 'गौतम', (3, 1): 'हरि', (3, 2): 'शर्मा'})
check('viewer table with multi-col body accepted by _isViewerTableReal', p._isViewerTableReal(mock_real_doc, None, 50, 3, 2), True)

# Filter fields for mock_blank_doc: table and cell fields must be stripped
blank_tbl_info = LineInfo('test', [])
blank_tbl_info.obj = mock_blank_doc
blank_tbl_fields = [
	FC('controlStart', TI.ControlField(role='table', **{'table-id': 50, 'table-rowcount': 3, 'table-columncount': 2})),
	FC('controlStart', TI.ControlField(role='cell', **{'table-id': 50, 'table-rownumber': 1, 'table-columnnumber': 1})),
	'शीर्षक',
	FC('controlEnd', None),
	FC('controlEnd', None)
]
filtered_blank = p._filterPdfViewerTableFields(blank_tbl_info, blank_tbl_fields)
check('viewer table with blank body has table/cell fields stripped', [f for f in filtered_blank if isinstance(f, FC)], [])
check('viewer table with blank body keeps text', ''.join(f for f in filtered_blank if isinstance(f, str)), 'शीर्षक')

print('FAILED' if bad else 'ALL OK', bad)
sys.exit(1 if bad else 0)


