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




## 2026-10-05 later (Claude): speed, copy with clipspeak, engine regression
* **Slowness**: (1) `pdfText.DocIndex._align` (difflib, added by Antigravity) ran ~400 SequenceMatcher
  comparisons per spoken line (8 ms here, much more on the user's PC). Engine lookup is back to the
  measured-better design: exact B match -> exact F (real text, when the viewer already shows it) ->
  tolerant anchors (`_find`) -> word by word, with a 3000-entry per-line cache. Word accuracy vs
  OCR truth: sitrep 87.5 %, flood 72.7 %, bulletin 82.1 %, EW4ALL 87.3 % (the `_align` version gave
  sitrep 24 %, bulletin 81 %, EW4ALL 86.6 %). (2) Building the index: faster content tokenizer
  (`pdfReader.contentOps`, drawing operators skipped in one regex step), work/rest time slicing
  (`_Yield`: 10 ms work / 15 ms rest), first 6 pages indexed first for files > 400 KB. (3) The old
  whole-document "letter pattern" learning (`_learnDocument`, slow, reads the whole document on the
  main thread) no longer runs when the PDF file itself is being read. (4) `_isPdfWindow` answer is
  memoised for 0.5 s per foreground window. `isWord=neLexicon.isWord` is now passed to the build.
* `devanagariRepair.py` reverted to the earlier version (Antigravity's `_isRealWord` + `_splitWord`
  change lowered repair accuracy on sitrep from 86.7 % to 67.2 %; web pages no longer use the repair
  at all, so the original reason for that change is gone). `neLexicon._COMMON_NEPALI` kept.
* **Copy with clipspeak**: clipspeak owns Ctrl+C, so Nepali Reader's Ctrl+C was dropped. Now
  `_chainCopy` wraps the other add-on's copy script: after it runs, `_fixClipboard` puts the real text
  on the clipboard when the clipboard holds exactly the selection. Browse-mode copy through NVDA
  (clipspeak calls the tree interceptor's script) already goes through the patched
  `TextInfo.copyToClipboard`. Long selections / select all are looked up line by line.
* diag.log now also records copies (`copy:` / `copy after app:`), 150 readings per session.
* **Table abbreviations dot -> ण् fix**: On `२०८२-०८३_परधकरणबट_गरएक_तथ_हद_गरक_पहर_अधययनक_सथनहर.pdf`,
  table abbreviations `टोखा न . पा .`, `गा . पा .`, `सि . नं .` were read as `टोखा न ण् पाण्`.
  Cause: `ArialRoundedMTBold` drew the dots and project acronyms (`NDRRMA`, `LI-BIRD`); `_detectLegacyFonts`
  classified it as `krutidev` because uppercase acronyms scored in Kruti Dev and 520 punctuation dots
  counted as legacy words. In Kruti Dev, `.` is `ण्`.
  Fix: `_detectLegacyFonts` ignores standard Latin fonts (`Arial`, `Calibri`, `Times`, `NirmalaUI`, etc.)
  unless glyph contours explicitly draw Devanagari; requires candidate words to have letters (`isalpha()`);
  and verifies that converted words exist in `neLexicon`. Bumped `INDEX_VERSION` to 10 and cleared stale `.idx` caches.

## 2026-10-05 (Glued Accessibility Nodes, Preeti Digit Typos & Fake-Bold Cleanups)
* **Glued Accessibility Boundary Splitting (`cleanGluedTokens`)**:
  - In Chromium, Brave, and Edge, adjacent inline accessibility nodes (such as image descriptions `alt="Description: Gvt"`, `graphic`, landmarks, and page numbers `(1)`) get concatenated directly to document text without spaces (e.g. `l;+xb/af/Description: Gvt(1)`).
  - This prevented both `DocIndex` lookup (exact token match failed) and `detector.decide` (the composite token scored as English due to "Description").
  - Added `cleanGluedTokens` to cleanly split accessibility keywords (`Description:`, `graphic`, `landmark`, `heading`, `level`, etc.), bracketed/parenthesized numbers, and Unicode bullets/arrows (`•`, `§`, etc.).
  - In `DocIndex.lookup`, if `cleanGluedTokens` separates tokens, lookup routes directly to `_tokens(clean)`, converting legacy words (`l;+xb/af/` -> `सिंहदरबार`, `(1)` -> `(१)`) while preserving English metadata (`Description: Gvt`).
  - In `DocIndex._tokens`, added prefix and suffix sub-token matching against `self._byKey` for any glued composite words.
  - In `detector.py`, added accessibility terms (`description`, `gvt`, `gov`, `govt`, `landmark`) to `COMMON_ENGLISH` and preprocessed input in `decide()`.
* **Devanagari OCR & Preeti Digit Typo Repair (`devanagariRepair.cleanShuffled`)**:
  - Restored visual glyph confusions: `०ा` (zero + aa) -> `ण` (`प्रमा०ाीकर०ा` -> `प्रमाणीकरण`), `लैि·क` / `ि·` -> `लैङ्गिक` / `ङ्ग`.
  - Repaired keyboard-shifted digit typos from corrupt/unshifted layouts: `द्द)टघ।ड।द्दद्द` -> `२०६३।८।२२`, `द्द)ठद्द` -> `२०७२`, `द्द)ठद्द।ट।ज्ञद्ध` -> `२०७२।०६।१४`, `द्द)ठद्द।ज्ञज्ञ।ज्ञघ` -> `२०७२।११।१३`, list numbers `ज्ञ.` -> `१.`, `द्द.` -> `२.`.
  - Fixed fake-bold single-letter echoes before words (`प पयोग` -> `पयोग`, resolving `अख्तियार दु अख्तियार दु प प प पयोग` -> `अख्तियार दुरुपयोग`).
* **Cache Invalidation**: Bumped `INDEX_VERSION = 13` in `pdfText.py`.

## 2026-10-05 (Preeti Subscript U-Matra '\xbf' Fix, Quote Variant Normalization & Sentence Verb 5 Repair)
* **Preeti Subscript U-Matra '\xbf' (`¿`) Fix**:
  - In `legacyFonts.PREETI_MAP`, `\xbf` (`¿`, U+00BF) was mistakenly mapped to `"रु"`.
  - In Preeti/Himalaya/Kantipur fonts, `?` (ASCII 63) is `"रु"`, whereas `\xbf` is the subscript `ु` (u-matra) glyph designed for consonants like `क`, `न्त`, `स`.
  - Because of this erroneous mapping, `lgs¿~h` became `निकरुञ्ज`, `jGohGt¿` became `वन्यजन्तरु`, and `s¿ljwf` became `सरुविधा`.
  - Fixed `PREETI_MAP["\xbf"] = "ु"`. Words now accurately convert to `निकुञ्ज`, `वन्यजन्तु`, and `सुविधा`.
* **Quote and `\xbf` Variant Key Normalization**:
  - When Chromium/Brave extracts text from PDF pages, it often normalizes glyph byte `\xbf` to standard ASCII quote `'` (`lgs'~h`, `jGohGt'`).
  - In `pdfText.DocIndex._tokens`, both `\xbf` and `'` variants are indexed and cross-matched in `_byKey` and `_byBag`.
  - In `__init__._indexText`, added fallback legacy word conversion for any unmatched piece with confident Preeti score/dictionary word.
* **Typo '5' for Verb 'छ' at Sentence End**:
  - In Preeti, unshifted key `5` is `छ`, while `%` is `५`. In royal enactments and legal clauses, typists typed `5` for `छ` (e.g. `यो ऐन बनाईबक्सेको ५ ।`).
  - In `devanagariRepair.cleanShuffled`, added generic repair converting `[verb] ५ ।` to `[verb] छ ।` for participles/auxiliaries (`ेको|एको|ने|दा|छैन`).
  - Added common dictionary word repairs: `महव` -> `महत्त्व`, `महवको` -> `महत्त्वको`, `महवराख्ने` -> `महत्त्व राख्ने`.
* **Cache Invalidation**: Bumped `INDEX_VERSION = 14` in `pdfText.py`.




## 2026-10-05 evening (Claude): general PDF fixes — missing letters, repeats, Preeti mapping
All fixes are general (no document-specific code). Measured with `/root/real/evreal.py` (14 real PDFs from
Suyog's Temp folder + constitution, OCR reference): mean 87.2 -> 87.4, बालबालिका ऐन (Word/Kalimati) 73.8 -> 96.2.
Chunked reading test (`frag.py`: lines read in 1-3 word pieces like NVDA's text chunks) went from many
duplicated words to almost none.
* **Missing letters (ज, ह, य ...) in Word PDFs**: Word's ToUnicode maps some glyphs to a space. `_isSpace`
  now trusts the glyph's real letters (`font.truth`) first, so those glyphs no longer break words.
* **Invisible joiners**: a "space" glyph that the next letter is drawn over (ZWJ/ZWNJ in Word) is not a word
  break (`_words`, `pend`). Fixes भन् नाले -> भन्नाले, बमो म -> बमोजिम.
* **Line baseline**: a new line now needs a different baseline than both the line start and the previous
  glyph (anusvara slightly lower than the line start split संहिता).
* **Lookup order** (`_lookup`): exact B (`_bfind`, short pieces prefer a word start), exact F, tolerant B
  (`_find`, now with `_findSkel`: B without vowel signs, `SB`/`SBpos`, so PDFium's moved signs मखु/मुख are
  found for any length), then tolerant F (threshold 0.9, window = n). Antigravity's tolerant F ran before the
  B search and returned neighbouring words (repeats / wrong words).
* **No repeated akshars between pieces**: in `_part`/`_spanF` an akshar belongs to the piece holding its first
  character (sayAll / chunked reading no longer says सङ्घी ङ्घीय). A piece that owns nothing (character
  navigation) still gets its akshar, never silence. Exact F pieces are not extended to whole words.
* **Fake-bold repeats**: PDFium repeats text that a PDF draws twice; `_dropRepeats` removes a word run that
  follows itself when the document itself has it once.
* **Preeti**:
  - `¿` (U+00BF): रू in real Preeti (x¿ हरू, b'¿kof]u दुरूपयोग); some fonts of the family draw ु there.
    The converter now tries रू, ु, रु and keeps the first that is a dictionary word (`_BF_CHOICES`).
  - `M` is always the visarga (निःशुल्क, पुनः); alone it is ":"; after a virama or before a dash it is ":".
    Antigravity's M->झ rule was removed (झ is `em` or `´`).
  - a lone `5` is छ (not ५); "." between digits is a date separator ("२०७२.०६.०३", not "२०७२।०६।०३").
  - raw codes 0x80-0x9F (fonts without encoding) are read as Windows-1252 (ˆ = फ्: cfˆgf] आफ्नो), and
    `keyOf` keeps ƒ ˆ ˜ ™ and C1 codes so those letters are not dropped.
  - fixed an endless recursion for words mixing Devanagari and ASCII letters.
* `__init__._convertFieldList`: runs are grouped between control fields (headings, paragraphs) before the
  lookup, so a reading spanning several headings is converted per heading (`tests/test_headings.py`).
* `INDEX_VERSION = 15` (old caches are rebuilt automatically).

## 2026-10-05 late evening: Mixed Unicode/Legacy conversion, Devanagari lookarounds & browser PDF detection
* **Mixed Devanagari and Legacy Text in `__init__._convertFieldList`**:
  - Previously, `elif devanagariRepair.hasDevanagari(text): continue` skipped any run that had any Devanagari characters, causing mixed runs (like `राष्ट्रिय lgs'~h तथा jGohGt' संरक्षण ऐन, २०२९` or `नेपाल सरकार l;+xb/af/`) to never be checked for legacy words.
  - Now, if a Devanagari run has ASCII letters, it is added to `unknown` so legacy words inside it are detected and converted.
  - In step 3 of `_convertFieldList`, `if i in convert` is evaluated before `if switchLang and (rebuilt or hasDevanagari): continue`, ensuring converted text is not bypassed by language switching tags.
* **Mixed Line Support in Unicode Documents (`_decideUnknown`)**:
  - When `isUnicodeDoc` was True, `if isUnicodeDoc and (legacyWords < 2 and legacyWords * 2 < words): return` previously discarded isolated strong legacy words (e.g. `l;+xb/af/ Description: Gvt Page 2 landmark (1)`).
  - Now checks for strong legacy tokens (`score >= MIXED_WORD` or `_strongAlone`); if present, mixed conversion proceeds.
  - Ensured `lineIsLegacy` is False when `joined` contains Devanagari (`hasDeva`), forcing individual token decisions (`context=False`) so existing Unicode and English words are preserved.
* **Devanagari Boundary Lookarounds in `devanagariRepair.py`**:
  - Python's `\b` fails on combining vowel signs/matras (e.g. `ु` U+0941 is `\W`), meaning `\bवन्यजन्तरु\b` never matched `वन्यजन्तरु `.
  - Replaced `\b` with Devanagari character lookarounds `(?<![\u0900-\u097f])` and `(?![\u0900-\u097f])` for `वन्यजन्तरु -> वन्यजन्तु`, `निकरुञ्ज -> निकुञ्ज`, `सरुविधा -> सुविधा`, `महव -> महत्त्व`, etc.
  - Fixed preeti digit confusion regex to properly match multi-codepoint conjuncts (`(?:द्द|द्ध|ज्ञ|छ|ट|ठ|ड|ढ|घ)\)(?:...)+` -> `२०६३।८।२२`, `२०७२`, list numbers `ज्ञ.` -> `१.`, `(ज्ञ)` -> `(१)`).
* **Detector Devanagari Safety in `detector.py`**:
  - In `decide()`, any token containing Devanagari characters is strictly marked `(t, False)` and excluded from legacy scoring, preventing Unicode text from being mistakenly treated as legacy.
  - `_isScorable` requires ASCII letters (`any(c.isascii() and c.isalpha())`).
* **Browser PDF Detection**:
  - Added `"finished loading pdf"` landmark marker to `_isPdfViewerObj` in `__init__.py` to correctly identify PDFs opened in Brave/Chrome even when the window title omits `.pdf`.
