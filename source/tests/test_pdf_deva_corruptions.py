import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fakenvda'))
import setup_fake as F

addon_dir = os.path.join(os.path.dirname(__file__), '..', 'addon', 'globalPlugins', 'nepaliReader')
sys.path.insert(0, addon_dir)

import neLexicon
neLexicon.load()

import devanagariRepair
import pdfText

print("Running test_pdf_deva_corruptions...")

# 1. Test _joinSplitWords on broken words separated by spaces in PDFs
samples_split = [
    ('बालबालिका सम् बन् धी कानूनलाई संशोधन र एकीकरण गन बनेको ऐन', 'सम्बन्धी'),
    ('परिच् छेद – १', 'परिच्छेद'),
    ('प्र चलित कानूनलाई संशोधन', 'प्रचलित'),
    ('वाञ् छनीय भएकोले', 'वाञ्छनीय'),
]

for orig, expected_sub in samples_split:
    fixed = devanagariRepair._joinSplitWords(orig)
    assert expected_sub in fixed, f"Expected {expected_sub} in {fixed} (from {orig})"
    print(f"ok   _joinSplitWords: {orig[:30]}... -> contains {expected_sub}")

# 2. Test DocIndex token reconstruction on balbalika PDF if present
pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'balbalika.pdf'))
if not os.path.exists(pdf_path):
    pdf_path = r'C:\Users\dhung\AppData\Local\Programs\antigravity\balbalika.pdf'

if os.path.exists(pdf_path):
    with open(pdf_path, 'rb') as f:
        data = f.read()
    idx = pdfText.DocIndex.build(data, maxPages=5)
    
    test_cases = [
        ('संवि २०७५ सालको ऐन नम्बर २३', 'संवत् २०७५ सालको ऐन नम्बर २३'),
        ('बालबालिका सम् बन् धी कानूनलाई संशोधन र एकीकरण गन बनेको ऐन', 'बालबालिका सम्बन्धी कानूनलाई संशोधन र एकीकरण गर्न बनेको ऐन'),
        ('प्रस्िवना', 'प्रस्तावना'),
        ('संरक्षण', 'संरक्षण'),
        ('प्र वरद', 'प्रवर्द्धन'),
        ('र पररपूलिन गरी', 'र परिपूर्ति गरी'),
        ('सवो', 'सर्वो'),
        ('सम् बन् धी प्र चलि कानूनलाई संशोधन र एकीकरण गन', 'सम्बन्धी प्रचलित कानूनलाई संशोधन र एकीकरण गर्न'),
        ('वाञ् छी भएकोले', 'वाञ्छनीय भएकोले'),
        ('संघी', 'संघीय'),
        ('संसदले ऐन बनाएको छ', 'संसदले ऐन बनाएको छ'),
        ('पररच् छेद', 'परिच्छेद'),
    ]

    for inp, expected in test_cases:
        res = idx.lookup(inp)
        assert res is not None, f"Expected lookup result for {inp}"
        got = ' '.join(p[0] for p in res if p[0])
        assert got == expected, f"Expected '{expected}', got '{got}' for input '{inp}'"
        print(f"ok   pdf DocIndex lookup: {inp[:25]}... -> {got}")

print("ALL PDF DEVANAGARI CORRUPTION TESTS PASSED!")
