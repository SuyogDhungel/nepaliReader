# A window is taken for a PDF from its title only when the title is that PDF's: a Teams window
# "Assignments | Example Open College | ..." is not the PDF whose title is "Example Open College"
# (Teams was read as that PDF, slowly). Run from the source folder: python tests/test_pdf_title.py
import os
import sys
import tempfile

home = tempfile.mkdtemp(prefix='nr_title_')
os.makedirs(os.path.join(home, 'Downloads'))
with open(os.path.join(home, 'Downloads', 'Course_Notes_Week1.pdf'), 'wb') as f:
	f.write(b'%PDF-1.4\n1 0 obj << /Title (Example Open College) >> endobj\n%%EOF\n')
os.environ['HOME'] = home
os.environ['USERPROFILE'] = home
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'addon', 'globalPlugins'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fakenvda'))
import setup_fake  # noqa: E402,F401
from nepaliReader import pdfLocate  # noqa: E402

failures = 0


def check(name, got, want):
	global failures
	ok = got == want
	if not ok:
		failures += 1
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))


pdf = os.path.join(home, 'Downloads', 'Course_Notes_Week1.pdf')
for title in ['Teams and Channels | Example Open College | student@example.edu | Microsoft Teams',
		'Assignments | (External) | Example Open College | student@example.edu | Microsoft Teams',
		'Science class, Monday | Example Open College | student@example.edu | Microsoft Teams']:
	check('not the PDF: ' + title[:40], pdfLocate._findRecentPdfByTitle(title), None)
check('the PDF shown under its own title', pdfLocate._findRecentPdfByTitle('Example Open College - Google Chrome'), pdf)
check('the PDF under its file name', pdfLocate._findRecentPdfByTitle('Course_Notes_Week1 - Google Chrome'), pdf)

print('\n%d failed' % failures if failures else '\nall passed')
sys.exit(1 if failures else 0)
