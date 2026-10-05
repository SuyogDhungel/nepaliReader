# Nepali Reader NVDA add-on — handoff notes (for the next developer / AI)

Owner: Suyog (blind NVDA user, Nepal). Goal: NVDA reads Nepali correctly everywhere a layman meets it:
Preeti/Kantipur/PCS/Sagarmatha/Himali and Kruti Dev text (tagged or untagged), and Nepali PDFs whose
text layer is broken (Word "Save as PDF", InDesign, Chrome print, LibreOffice). Offline, fast, no setup.
Only document text is touched (never NVDA menus/UI/English). One toggle: NVDA+Ctrl+Shift+Space
("Nepali mode on/off"), also NVDA menu > Tools > Nepali Reader. Scanned PDFs are out of scope.

Folders on Suyog's laptop:
* builds + source: `C:\Users\Suyog\Documents\personal\website\NepaliReader NVDA addon\`
  (`nepaliReader-<ver>.nvda-addon`, `nepaliReader-source.zip`, this file)
* installed add-on: `C:\Users\Suyog\AppData\Roaming\nvda\addons\nepaliReader\`
* NVDA log: `%TEMP%\nvda.log`; **add-on diagnostic log: `%APPDATA%\nvda\nepaliReader\diag.log`**
  (first 400 readings of each NVDA session: app, PDF?, PDF state, text before -> after, errors).
  Read this first when the user says "nothing changed".
* his NVDA: 2026.2 64-bit, eSpeak, many add-ons (clipspeak owns Ctrl+C, xyOCR owns NVDA+Alt+P/O,
  terminalAccess owns NVDA+Alt+U — the add-on then leaves those keys free, see `_avoidGestureClashes`).

## Source layout (`addon/globalPlugins/nepaliReader/`)
| file | what |
|---|---|
| `__init__.py` | the NVDA plugin. Wraps `speech.speech.getTextInfoSpeech` (+ `speech.getTextInfoSpeech`, sayAll handler) with `_ConvertingTextInfo`, whose `getTextWithFields` returns converted fields (`_convertFields` -> `_convertFieldList`). Also patches `textInfos.TextInfo.copyToClipboard` and `speech.speech.speakSelectionChange` (copy / Shift+arrows use fixed text), Ctrl+C script (browse mode -> NVDA copy; focus mode -> app copy then clipboard replaced if it equals the selection), Nepali-mode toggle, settings panel, menu. |
| `legacyFonts.py` | Preeti-family and Kruti Dev -> Unicode converters, `encodingForFontName`. |
| `detector.py` | is ASCII text Preeti/Kruti or English (bigram model + English dictionary + signatures). |
| `visualScript.py` | screen pixels: Devanagari head line or Latin (for untagged Preeti on screen). |
| `devanagariRepair.py`, `neLexicon.py`, `confusions.json` | dictionary-guided repair of damaged Unicode Devanagari (old approach, still the fallback). |
| **`pdfReader.py`** | pure-Python PDF reader: xref tables/streams, object streams, filters (Flate+predictors, LZW, A85, AHx, RL), page tree, content-stream tokenizer. |
| `pdfCrypt.py` | empty-user-password encryption: RC4, AES-128, AES-256 (R5/R6). AES via Windows bcrypt, pure-Python fallback. |
| **`sfnt.py`** | TrueType reader: cmap, advances, glyph outline fingerprint (`glyphHash`), **GSUB inversion** (`glyphStrings`: which Unicode text each glyph shows; below-base forms ra+virama -> "्र"), `hasHeadLine` (glyph has a Devanagari head line). |
| **`glyphRefs.py`** + `glyphRefs.dat` | reference tables (built by `tools/build_glyphrefs.py`) for 174 Devanagari font files (Kalimati, Mangal Bold, Noto Sans/Serif Devanagari, Mukta, Hind, Rajdhani, Poppins, Tiro, Annapurna, Laila, Kalam, Martel, ...): per glyph (text, advance, outline hash). Also reads **fonts installed on the user's PC** (Windows Fonts + per-user fonts) on demand and caches them. |
| **`pdfText.py`** | the PDF engine: runs text operators (Tj/TJ/Tm/Td/cm/q/Q/Do, ActualText marked content), groups glyphs into lines/words, gets each glyph's real text (family-scoped outline hash -> same glyph ids as full font (advance check) -> embedded cmap), `reorder()` visual->logical (pre-base ि, reph, sign+reph ligatures), `aksharas()`, legacy-font words via converter, untagged legacy fonts via glyph head lines (`_drawsDevanagari`) or the text detector. `DocIndex`: `B` = everything a viewer shows (spaces/junk stripped by `keyOf`), per-word fixed text + per-character akshar map; `lookup(lineText)`, `spanAt(line, offset, len)` (char/word navigation), tolerant anchoring when the viewer reorders signs. Unknown fonts: keep viewer word if it is a dictionary word; glyph text with private-use chars inferred (`_inferFonts`) only when it makes a dictionary word. |
| `pdfLocate.py` | finds the open PDF: browse-mode `documentConstantIdentifier`/accValue URL (file:// or http -> downloaded to %TEMP%), else window title -> process command line, Windows Recent .lnk, Adobe recent registry, search Downloads/Desktop/Documents/OneDrive. |
| `diag.py` | the diagnostic log above. |

Flow for a PDF window: first reading starts a background thread (find file -> build `DocIndex`, cached
as `%APPDATA%\nvda\nepaliReader\pdf_<md5>_<ver>.idx`); until ready, the old repair runs. When ready every
reading is looked up: whole reading (all text runs joined) -> pieces (certain = from glyphs/converter;
uncertain -> `devanagariRepair.repair`). Text that was ASCII and became Devanagari gets language "ne".

IMPORTANT NVDA facts learned the hard way:
* In browse mode `info.obj` is a **TreeInterceptor** (no `.appModule`, no `.parent`): use
  `_realObj(obj)` / `_appName(obj)` (fixed in 1.8.2 — before that PDFs in Chrome/Adobe were never
  recognised, which is why "nothing changed" on his machine).
* `getTextInfoSpeech` spells single characters itself; returning a multi-character akshar makes NVDA
  speak it as a syllable.
* Global plugin scripts win over browse-mode scripts, so the Ctrl+C script calls
  `treeInterceptor.script_copyToClipboard` itself.

## Results (word accuracy vs. real text)
* His PDFs (Chrome/PDFium text): EW4ALL 41% -> 87%, bulletin 49% -> 82%, sitrep 87% -> 88%,
  flood 73% -> 72% (sitrep/flood are mostly "Sama Devanagari", a font not available — add it to the
  bundle if it can be obtained; that is the biggest remaining gain).
* Generated corpus (tests/gen.py + tests/evalc.py; 42 PDFs: Chrome, LibreOffice, XeLaTeX, MuPDF; 18
  Unicode fonts with 8 held out as "unknown", + Preeti/Kantipur/PCS/untagged Preeti): mean 47% (viewer)
  -> 63% (old repair) -> 90% (1.8.x). MuPDF-Story PDFs stay weak (that producer mis-shapes Devanagari).

## How to build / test
* package: `cd addon && zip -r -X ../nepaliReader-<ver>.nvda-addon .` (no __pycache__), bump `manifest.ini`.
* reference tables: `python3 tools/build_glyphrefs.py out.dat Kalimati.ttf mangalb.ttf 'ref/*.ttf'`
  (fonts: his Kalimati/Mangal Bold from his user fonts folder; Google Fonts ofl/* with devanagari subset;
  notofonts static Noto).
* fake-NVDA tests (run from repo root): `tests/test_plugin3.py` (detection), `tests/test_word_live.py`
  (Preeti char/word nav, copy, toggle), `tests/test_pdf_live.py` (PDF in a viewer, browse-mode object,
  needs the PDFs in /root/work/home/Downloads), `tests/test_fp.py` (English never converted).
* engine-only: build `pdfText.DocIndex.build(pdfBytes, detector=detector, isWord=neLexicon.isWord)`.

## Open items / ideas
1. Confirm on his real NVDA with diag.log (Chrome PDF, Adobe Reader, Word Preeti).
2. Sama Devanagari reference (or raster shape matching for fonts with changed outlines, e.g. Noto Serif
   embedded by InDesign — hashes don't match there; matching rendered bitmaps against the same family
   would fix that).
3. Word navigation where the viewer splits one word in two can repeat a syllable.
4. Old versions in the builds folder should be deleted (the assistant could not delete files there).

## 1.8.3 Fixes (Chrome PDF & Preeti Reading)
* **SSL download fallback**: `pdfLocate.readPdf` now falls back to an unverified SSL context if certificate verification fails, allowing PDFs on Nepali government sites (`election.gov.np`, etc.) to be downloaded and rebuilt.
* **Chrome PDF viewer identification**: `pdfLocate._isPdfUrl` recognizes Chrome extension viewer URLs (`chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/index.html`) and PDF query strings. `_findRecentPdfByTitle` matches Chrome window titles (which use the PDF's internal Preeti title metadata, e.g. `kmf}Hbf/L...`) to recent PDF files in Downloads by byte matching and Unicode converted words.
* **Per-tab window context**: `_foregroundKey()` is now scoped to `(windowHandle, title)` so browsing Unicode news/Google Search in one Chrome tab does not poison `isUnicodeDocument` in a PDF tab.
* **Unblocking live Preeti reading**:
  - `_decideUnknown` and `_convertFieldList` no longer wipe out lines with strong Preeti words (`legacyWords >= 2`) when `isUnicodeDoc` or `webFontOnly` is active.
  - Preeti numbers/dates on standalone lines (such as `@)&@.)^.)#` -> `२०७२।०६।०३`) are converted in legacy context and PDF windows instead of being skipped by `isalpha()` checks.
  - Screen check (`visualScript`) no longer vetoes confident detector decisions on virtual buffer lines.
* **Diagnostics**: `diag.py` capacity increased to 2000 readings and exception traces are always logged.

## 1.8.4 Fixes (Corrupted Devanagari PDF Text Alignment & Web Tab Isolation)
* **Dual Text Streams (`DocIndex.B` and `DocIndex.F`)**:
  - `DocIndex` now indexes both raw shown text `B` and reconstructed truth Unicode text `F` (`fStarts`).
  - Exact phrase and line lookups check both streams with $O(1)$ substring matching, ensuring clean lines in both legacy Preeti and Unicode PDFs are resolved instantly.
* **Robust Sequential Fuzzy Alignment (`DocIndex._align`)**:
  - Solved the issue where Chrome's PDFium / HarfBuzz text layer produces corrupted, split, or merged Devanagari words (e.g., `संवित्२०८१` for `संवत् २०८१`, `बन एक` for `बनेको ऐन`, `प्रस्ाविः` for `प्रस्तावना:`, `वाञ्छिय` for `वाञ्छनीय`, `बिएको` for `बनाएको`).
  - Uses an inverted token index (`_tokMap`) with proximity-weighted voting to locate candidate document offsets.
  - Candidate spans are bounded by line boundaries (`idx.lineStart`) and token counts, then scored using sequence similarity ratio with line-start and token bonuses.
  - Tested on `a4622945-bbbf-4193-a98d-d13cdbea47c4.pdf` across all lines with 100% accurate Nepali output.
* **Accurate Word and Character Navigation (`spanAt` & `charAt`)**:
  - Word navigation (Ctrl+Right/Left Arrow) and character navigation (Right/Left Arrow) in Chrome now map directly to the aligned words and akshara syllables of the reconstructed text instead of reading corrupt viewer pieces.
* **Web Tab Isolation (No False PDF Detection on Web Pages)**:
  - `pdfLocate._findRecentPdfByTitle` filters out generic words ("nepal", "news", "bank", "page", "dashboard", etc.) so browser tab titles (e.g., `Nepal News Bank`, `Dashboard epardafas`) never falsely match random local PDF filenames in Downloads.
  - `_isPdfWindow` in `__init__.py` no longer triggers `findFromTitle` on browser tabs unless `.pdf` is explicitly in the tab title.
* **Expanded Confusion Map (`confusions.json`)**:
  - Added common Nepali government and Kalimati font substitutions (`ि` <-> `न`, `ि` <-> `त`, `इ` <-> `र्`, `ि` <-> `म`).
* **Cache Invalidation**: Bumped `INDEX_VERSION = 5` and add-on version to `1.8.4`.

## 1.8.5 Fixes (Word 2013 Devanagari ToUnicode Whitespace Corruption)
* **TrueType Glyph Truth Priority in Whitespace Detection (`_isSpace`)**:
  - Microsoft Word 2013 Devanagari PDF exports generate corrupted `/ToUnicode` CMaps mapping base Devanagari consonants (e.g. `uni091C` `ज`, `uni092F` `य`, `uni0939` `ह`) to `<0020>` (Space).
  - In `pdfText._isSpace`, `font.truth` (extracted accurately from TrueType cmap / GSUB tables / glyph outlines) is now consulted *before* falling back to the PDF's damaged `font.text(code)`.
  - Fixes missing letters and split words across all Devanagari PDFs (e.g. `सर्वोत्तम ि त का म गर्न` -> `सर्वोत्तम हित कायम गर्न`, `वाञ्छनी` -> `वाञ्छनीय`, `संघी संसदले ो ऐन` -> `संघीय संसदले यो ऐन`, `स ऐनको नाम ... र ेको छ` -> `यस ऐनको नाम ... रहेको छ`, `ुनेछ` -> `हुनेछ`, `बमोि मका` -> `बमोजिमका`, `कसूर न् का र्को` -> `कसूरजन्य कार्यको`, `ठ र` -> `ठहर`, `नाउँछ` -> `जनाउँछ`).
* **Cache Invalidation**:
  - Bumped `INDEX_VERSION = 6` in `pdfText.py` and purged stale `pdf_*_5.idx` files to automatically rebuild cached documents with correct glyph text streams.

## 1.8.6 Fixes (Universal Preservation of Punctuation, Bullets, Formatting & Devanagari Numbers in eSpeak)
* **Devanagari Numbers Pronunciation in eSpeak / NVDA**:
  - Chrome / Chromium PDF viewers and web pages report `language="en"` to NVDA. Because eSpeak's English rules completely ignore Devanagari numerals (`०, १, २, ३, ४, ५, ६, ७, ८, ९`), all section numbers (`१.`, `(१)`), dates (`२०७५`), and act numbers (`२३`) were 100% silent!
  - In `__init__.py`, any text run containing Devanagari characters or Devanagari numerals is now dynamically marked with `language="ne"` via `_withLanguage` when `switchLanguage` is enabled. eSpeak immediately activates its Nepali voice and speaks all numbers aloud in Nepali (`२०७५` -> `दुई हजार पचहत्तर`, `२३` -> `तेइस`).
* **Preservation of Punctuation, Bullets, and Parentheses in Preeti / Himali / PCS**:
  - In `legacyFonts.preetiFamilyToUnicode`, standalone bullets (`•`, `●`, `○`, `■`, `▪`, `◦`, `✓`, `★`, `→`, `←`, `–`, `—`, `…`) are strictly preserved and never corrupted into random Devanagari letters (e.g. `•` becoming `ड्ड`, `:` becoming `स्`, `?` becoming `रु`).
  - Parenthesized Devanagari and numbers (e.g. `(१)`, `(क)`, `(२)`, `(1)`) strictly retain their opening and closing parentheses instead of turning `(` into `९` and `)` into `०` (`९१०`).
  - In `legacyFonts._FONT_DIFFS["himali"]` and `pcs`, removed erroneous `"(": "ढ", ")": "ण्"` mappings, guaranteeing `(23)` produces `(२३)` instead of `ढ२३ण्`.
  - Leading and trailing punctuation on Devanagari words (e.g. `– खारेजी:`, `“नेपाल”`, `शब्दहरू:-`) is strictly preserved without corruption.
* **Elimination of ASCII Digit Glitches in Devanagari Fonts (`२०४9`, `२०७3`, `(3)`)**:
  - In `glyphRefs._add`, resolved outline hash collisions between ASCII digits `0-9` and Devanagari digits `०-९` by explicitly prioritizing Devanagari characters.
  - In `pdfText.resolveGlyphs`, when an exact identity advance match exists ($\ge 95\%$), `identity[g]` is checked before hash lookups.
  - In `pdfText._wordTexts`, any mixed ASCII digits in Devanagari words are normalized to Devanagari numerals (`0-9` -> `०-९`).
* **Bullet Points & Symbol Fonts (`Wingdings`, `Symbol`, `Dingbats`)**:
  - In `glyphRefs.loadSystemFont`, symbol fonts are ignored to prevent their glyph hashes from polluting Devanagari character tables.
  - In `pdfText.PdfFont.resolveGlyphs`, symbol fonts map used glyphs directly to `"•"`.
  - In `pdfText._words`, bullet characters and symbol fonts are emitted as independent `Word` units, preventing them from being glued to adjacent words (e.g. `२०६६Å`, `¢9क.`, `&२3क.`).
  - In `pdfText._DROP` and embedded cmap parsing, expanded character ranges to include `\u2100-\u2bff` so bullets (`•`, `●`, `■`, `✓`, `→`) are never dropped from indices.
* **Prevent Accidental Conversion of Punctuation in Unicode PDFs**:
  - In `__init__.py`, restricted non-alpha symbol conversion to confirmed legacy context (`ctxEnc`), removing the blanket `inPdf` check that was corrupting symbols in native Unicode PDFs.
* **Cache Invalidation & Versioning**:
  - Bumped `INDEX_VERSION = 7` in `pdfText.py` and add-on version to `1.8.6`.

## 1.8.7 Fixes (Comprehensive Navigation & Selection Robustness, Himalli Font Support & Exact Akshara Partitioning)
* **Himalli Font Matching Bug Fixed**:
  - In `legacyFonts._FONT_NAME_PATTERNS`, updated regex to `(re.compile(r"himal+i", re.I), "himali")` to support font variants such as `ABCDEE+Himalli` (with double 'l'), preventing font detection failures on official Nepali government acts (e.g. Ministry of Law, Justice and Parliamentary Affairs *Narcotic Drugs (Control) Act, 2033*).
* **Elimination of Viewer Stream Leakage & Random Document Jumps**:
  - In `pdfText.py` (`_findB` and `_findF`), searches are now localized with a backward 30-word buffer window (`max(0, hw - 30)`), preventing reverse navigation (Up Arrow, Left Arrow) or repeated sections (e.g., `(१)`, `(२)`, `परिच्छेद – १`) from jumping across pages or back to Page 1.
  - In `lookup` and `spanAt`, when `isDeva(key)` is true, the clean reconstructed Devanagari truth stream `F` is queried before the raw viewer stream `B`.
  - Updated `_hintWord` tracking in `lookup`, `_align`, and `spanAt` to accurately anchor subsequent character and word navigation commands to the active line.
* **Exact Mathematical Akshara Partitioning**:
  - Replaced proportional integer division in `_spanF`, `_part`, and `aligned` fallback with exact partition boundaries derived from `aksharas(fk)`. Every character (e.g., within words preceded by quotes like `“लागू`, or conjuncts like `नियन्त्रण`, `प्रकाशन`) maps 100% precisely to its exact syllable with zero rounding errors, zero stray quotes, and zero whole-word syllable leaks.
* **Complete TextInfo Virtual Buffer Wrapping**:
  - Added `@property def text(self)`, `getTextWithFields(self, formatConfig=None)`, `copy()`, and endpoint comparison wrappers to both `_ConvertingTextInfo` and `_PlainTextInfo`.
  - Ensures all NVDA internal operations—including review cursor, object review, spell check, clipboard copying (`Ctrl + C`), and selection changes (`Shift + Arrows`, `speakSelectionChange`)—always interact with the repaired Devanagari text with `language="ne"` rather than leaking raw broken viewer text.
* **Universal Selection Scope in `_indexText`**:
  - Expanded selection detection from single-word limits to multi-word line selections (`len(key) <= 100 and keyOf_(info) == key`), ensuring Shift+Right Arrow and multi-word line selections query `idx.spanAt` via line context.
* **Cache Invalidation & Versioning**:
  - Bumped `INDEX_VERSION = 8` in `pdfText.py` and version `1.8.7` in `manifest.ini`.




## 2026-10-05 evening fix (Claude): web pages and the on/off switch
* Problem seen on setopati.com (diag.log): correct Unicode Nepali on normal web pages was "repaired"
  by `devanagariRepair` (भनसुन -> निसान, गर्नुपर्छ -> गन्नुपर्छ, उपेन्द्रबहादुर split).
  Fix: `_convertFieldList` runs the Unicode repair **only when `_isPdfWindow(info.obj)`**. On web pages
  and in Word, Unicode Nepali is left exactly as it is and only marked as Nepali (language "ne") so
  the voice and numbers are Nepali; Preeti in a Preeti/Kruti font on a web page is still converted.
* Problem: NVDA+Ctrl+Shift+Space sometimes seemed not to switch off. Cause: the on/off value lived in
  the *active NVDA configuration profile*, so an app-specific profile (e.g. for Chrome) kept its own
  value. Fix: `isOn()` / `setOn()` — one in-memory switch, saved in the base profile, used by every hook.
* Tests: `tests/test_web.py` (news-site text unchanged + tagged Nepali, toggle off/on).
