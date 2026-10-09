# Changelog

All notable changes to the **Nepali Reader** NVDA add-on are documented here.

## [2.0] - 2026-10-09

### Changed
- **Shortcut Key Streamlining**: Redundant shortcut keys to activate and deactivate Nepali mode were removed. Only `NVDA + Ctrl + Shift + Space` toggles Nepali mode on or off, and `NVDA + Ctrl + L` directly opens the Nepali Reader settings dialog. `Ctrl + C` continues to copy clean Unicode text.

### Added
- **In-App Update Progress**: Update download with a live progress dialog (`Connecting to server...`, `Downloading update, please wait... X%`), cancel support, IPv4-first connection for slow ISP routes, automatic hand-off to NVDA's own add-on install dialog, and plain-text release notes for screen readers (by Roshan Gautam).
- **Project Authorship**: Maintained by Suyog Dhungel and Roshan Gautam.
- **Integrated GitHub Auto-Updater**: Built-in automatic update engine checking GitHub releases. Users receive update notifications with one-click background download and installation without needing external websites or manual downloads. Added a manual "Check for updates..." item under NVDA's Tools menu and a toggle in Nepali Reader settings.

### Fixed
- **Copy in browse mode when Nepali mode is off**: Ctrl+C now always uses NVDA's own browse mode copy, so copying works with the add-on switched off (by Roshan Gautam). Conflict with ClipSpeak resolved.
- **Fully inactive when switched off**: The MultiLang language hooks now do nothing while Nepali mode is off (menu or shortcut), so MultiLang behaves exactly as without the add-on.
- **English stays English when reading character by character or word by word** in documents that mix Preeti and English (Word, Notepad, browsers, PDFs). Before, an English letter was spoken as a Nepali letter. Character and word reading now follow exactly what line reading decides for the same word; in PDFs the document's own letter is used. Typing echo and spelling are never converted.
- **Unicode PDF Window Title & Filename Speech Normalization**: Permanently fixed speech announcements for government PDF filenames, URLs, and window titles with stripped matras (e.g. `२०८३-०६-२०_दनक_वपद_बलटन.pdf` is spoken naturally and accurately as `२०८३-०६-२० दैनिक विपद् बुलेटिन` in File Explorer, Brave, Chrome, and Edge) without altering files on disk.
- **Many Preeti Reading & Pronunciation Fixes**: Resolved orthographic syllable parsing and ligatures for complex Nepali clusters and vowel combinations.
- **Literal Number & Clause Integrity**: Eliminated speculative word substitutions at sentence boundaries; genuine digits (`५` / `5`), numbered clauses, and legal section references remain intact as numbers without false-positive alterations.
- **1:1 Selection and Clipboard Copying Fidelity**: Guaranteed synchronized Unicode Devanagari copying (`Ctrl+C`, `Ctrl+A`) matching spoken text across browse mode and review cursors.
- **PDF text is read exactly as written**: words rebuilt directly from the PDF (for example सुदुर, शम्शेर, वापत, शिव भक्त) are no longer "repaired" a second time by the speech filter, which had changed them (सदर, शमशेर, वापस, शिवभक्त).
- **Preeti numbers typed with the number row** (for example `!(*)` for १९८०, `@)&*` for २०७८, `!$` for १४) are converted instead of being treated as bullets or symbols. English text such as (2024), 50% and #1 is unchanged.
- **Digits and signs are read as shown**: reading a Devanagari number character by character (for example वि.सं. १९८०) spoke ज्ञ ढ ड instead of १ ९ ८, and a word such as ना२ख (a number plate) was rewritten as नाद्दख. A digit now becomes a letter only where the Nepali dictionary proves that the word is meant (बा६ is बाट, यु४ is युद्ध). Words on the web that end in ! or % (for example "गर्नुपर्छ!") were also changed (to गर्नुपर्छज्ञ); they are left as they are.
- **Spellings are not "corrected"**: सुदुर is read as सुदुर (not सदर), and two real words with a space between them (प्रधान मन्त्री, चन्द्र शम्शेर) are no longer glued into one word. Words rebuilt from a PDF are not repaired a second time, so न.पा. stays न.पा.
- **Word reading follows line reading for Preeti numbers**: a year such as @)&@ is spoken २०७२ when read word by word, as it is when read by line. A lone ( or ) between two Preeti words is the digit key and is read ९ or ०; brackets typed as - and _ and clause marks such as (क) are unchanged.
- **Character reading**: ि is spoken as ि (an internal marker was reaching the speech), and the keys o and f in भयो (eof]) are no longer read together as ध.
- **PDF digits and bullets**: a lone ( or ) in a Preeti PDF line (for example "९ जना रानी") is read ९ or ०; the Courier "o" bullet is read as ○; a lone 5 in a Preeti line is छ; the keys ÷ and § stay inside words (दुईपट्टी, आदिवासी/जनजाति).
- **Character reading in PDFs**: digit and sign keys inside Preeti words (for example the 8 in चा8) now read as the letter they are (ड), matching line reading.
- **Decimals in PDFs**: ६.)% is read ६.०% (a ")" after a digit and a point is the digit key for ०).
- **Quiet releases**: the automatic update check only notifies when the GitHub release notes contain the word [notify]. Releases without it are still found by "Check for updates...", and the next [notify] release carries every earlier fix.

## [1.1.6] - 2026-10-07

### Added
- **Comprehensive Preeti & Legacy Font Extended ASCII / Alt-Code Integration**: Synthesized complete glyph tables from top open-source Devanagari conversion engines (*Shuvayatra/preeti*, *Rachana-Labs/nepali_pdf_parser*, *casualsnek/npttf2utf*, *cimplesid/unicode-preeti-js*). Added full support for Alt-codes 128–255 including byte 149/0x95 (`•` -> `ड्ड` in words such as `c•f` -> `अड्डा`), 236/0xEC (`ì` -> `त्त्`), 134/0x86 (`†` -> `!`), 145/0x91 (`‘` -> `ॅ`), 222/0xDE (`Þ` -> `़` nukta), and English loan-vowel candra compositions (`अाॅ` -> `ऑ`, `ाॅ` -> `ॉ`, e.g., 'कलेज', 'अफिस').
- **Additional Nepali Font Family Recognition**: Added dedicated aliases and patterns for standard government/newspaper font families: **Gorkhapatra**, **Ganess**, and **NayaNepal**.
- **Bullet & Symbol Preservation**: Standalone bullet characters (`•`, `●`, `○`, `■`, `▪`, `★`) in lists and outlines are strictly preserved as bullets, while byte 149 inside Preeti words correctly transforms to `ड्ड`.

### Fixed
- **Robust Character Navigation Across All Document Formats**: Enhanced `_resolveCharacter` (`Left/Right Arrow`) to inspect adjacent character buffers whenever virtual buffers or PDF inline spans disconnect line/word contexts. Prevents silent letter drops or raw digits (`६`, `८`) from being spoken.
- **Flawless Multi-Directional Navigation & Selection**: Guaranteed 100% precision for line-by-line reading (`Up/Down Arrow`), word-by-word reading (`Ctrl+Left/Right Arrow`), character review (`Left/Right Arrow`), range selection (`Shift+Arrows`, `Ctrl+Shift+Arrows`), and clean Unicode clipboard copying (`Ctrl+C`, `Ctrl+A`) across both Unicode Devanagari and legacy Preeti texts.
- **Universal Hybrid Residue Repair**: Automatically detects and repairs damaged hybrid signatures (`पाठ्यव्रम`, `रहेका]`, `कुन}`, `पुर}`, `प्रविधिबा६`, `रेक८र्`, `गनर्`) across any window or browser view while keeping clean Devanagari text on web pages 100% untouched.

## [1.1.5] - 2026-10-07

### Added
- **Seamless MultiLang Add-on Integration**: Full automatic integration with the popular MultiLang virtual synthesizer add-on. When MultiLang is active, Nepali Reader ensures Devanagari text is accurately recognized as Nepali (`ne`) rather than forced to Hindi (`hi`).
- **Automatic Supporting TTS Voice Discovery**: Automatically resolves and activates the best available Nepali voice across installed synthesizers—including Hear2Read Indic Voices (`Hear2ReadNG` with Google Nepali neural voice) and eSpeak NG (`ne`)—even without manual profile configuration in MultiLang.
- **Word Document Proofing Language Override**: Overrides Microsoft Word's default `hi-IN` language tagging on Devanagari paragraphs whenever the vocabulary is identified as Nepali, ensuring MultiLang and NVDA switch to the Nepali voice rather than Hindi.

### Fixed
- **Character Navigation & Residue Elimination**: Context-aware single character resolution (`Left/Right Arrow`) now maps and speaks clean Devanagari characters from surrounding word context. Resolves Preeti digit keys (`प्रविधिबा६` -> `प्रविधिबाट`), inverted reph (`गनर्` -> `गर्न`, `रेक८र्` -> `रेकर्ड`), and legacy bracket residue (`पाइन]` -> `पाइने`, `पहिला]` -> `पहिलो`) during character review without double-reading or landing on raw digits or brackets.
- **Decomposed Matra Normalization**: Full composition for decomposed Devanagari vowel signs (`ा` + `े` -> atomic `ो`, `ा` + `ै` -> atomic `ौ`, `अ` + `ो` -> `ओ`, `अ` + `ा` -> `आ`, `ए` + `े` -> `ऐ`). Eliminates split vowel pronunciation (e.g. `पहिलाे` read as separate `ा` and `े` or "पहिला" + "का").
- **Glued Preeti Digit Resolution**: Automatically detects single unshifted Preeti digit keys embedded directly inside Devanagari words (`६` -> `ट`, `८` -> `ड`, `३` -> `घ`, `४` -> `द्ध`, `१` -> `ज्ञ`, `२` -> `द्द`, `७` -> `ठ`, `९` -> `ढ`, `०` -> `ण`) while strictly preserving standalone numbers, dates (`२०७८`), decimals, percentages, and list items.
- **Post-Consonant Reph Inversion**: Automatically corrects Preeti typing order reph (`\u0930\u094d`) trailing after consonants and matras (`गनर्` -> `गर्न`, `रेकडर्` -> `रेकर्ड`, `कमर्` -> `कर्म`, `धमर्` -> `धर्म`, `वषर्` -> `वर्ष`, `खचर्` -> `खर्च`, `पूणर्` -> `पूर्ण`, `गदार्` -> `गर्दा`, `गनेर्` -> `गर्ने`) at word boundaries and before postpositions.
- **Accurate Devanagari Clipboard Copying & Selection Speech**: `Ctrl+C`, `Ctrl+A`, and `Shift+Arrows` now repair hybrid Devanagari residue on the fly, ensuring clean Unicode Devanagari is copied to the clipboard and spoken aloud.
- **PDF Browser & Viewer Hybrid Devanagari Repair**: Fixed an issue where PDF viewers (Chrome, Edge, Acrobat) exposed legacy font names on already-extracted Devanagari text, which previously caused Devanagari repair to be bypassed. Now eliminates legacy residue across all viewers: `रहेका] छ` -> `रहेको छ`, `केन्द्रका]` -> `केन्द्रको`, `यसका] पुर}` -> `यसको पुरै`, `कुन}` -> `कुनै`, `पाइन]` -> `पाइने`, `पहिला]` -> `पहिलो`, `हाम्रा]` -> `हाम्रो`, `शिक्षाल]` -> `शिक्षाले`.
- **Strict Grammatical Fidelity & Vibhakti Preservation**: Strictly preserves all grammatical forms and vibhaktis according to actual text without artificial overwrites: `को` (singular genitive), `का` (plural/honorific genitive), `की` (feminine genitive), `रो`/`रा`/`री` (`मेरो`/`मेरा`/`मेरी`, `हाम्रो`/`हाम्रा`/`हाम्री`), `नो`/`ना`/`नी` (`आफ्नो`/`आफ्ना`/`आफ्नी`). Resolves legacy residue (`नेपालका]` -> `नेपालको`) and decomposed matras (`क\u093e\u0947` -> `को`) without ever altering genuine `का` (e.g. `रामका छोराहरू`, `नेपालका नदीहरू`, `सबैका लागि`).
- **Valid Prefix & Reph Stem Protection**: Valid Sanskrit/Nepali prefixes ending in reph like `पुनर्` (`पुनर्विचार`, `पुनर्स्थापना`) are strictly protected from reordering and are never flagged as corrupted hybrid residue.
- **Preeti/Himali `क्र` Modifier Conjuncts**: Extended glyph modifier resolution for `व` + `्र` (`व्रम` -> `क्रम`, `व्रिया` -> `क्रिया`, `व्रे` -> `क्रे`, `व्रा` -> `क्रा`, `व्री` -> `क्री`), restoring `पाठ्यव्रम` -> `पाठ्यक्रम`, `कार्यव्रम` -> `कार्यक्रम`, `उपव्रम` -> `उपक्रम`, `प्रव्रिया` -> `प्रक्रिया`, `व्रियाकलाप` -> `क्रियाकलाप`.
- **Preeti Vowel & Alphabet Completeness**: Added `("एै", "ऐ")`, `("अो", "ओ")`, `("अौ", "औ")` compositions, rakar conjunct deduplication, 100% full coverage for extended Alt-code characters, and refined number regex so words like `3/` correctly convert to `घर`.
- **PDF Index Exact Key Alignment**: Optimized `DocIndex.lookup` to prioritize clean keys before fuzzy matching, guaranteeing exact sentence reconstruction from underlying PDF text streams without bleeding boundary words.
- **Himali Downward U-kar (`\xac` / `¬`)**: Added missing `\xac` Alt+0172 character to `PREETI_MAP`, fixing words like `स¬झावहरू` -> `सुझावहरू`.
- **Number Preservation in MultiLang**: Prevented MultiLang from dropping Devanagari numerals (`०-९`) and numbers attached to Nepali clauses into English speech.


## [1.1.4] - 2026-10-06 (Stable Release)

### Fixed
- **Double Character Reading Elimination**: Character navigation (`Left/Right Arrow`) in both Preeti and Unicode Devanagari now speaks the exact letter or matra without repeating syllables or characters twice.
- **Native Unicode Selection & Copying**: Copying (`Ctrl+C`, `Ctrl+A`) and selection navigation (`Shift+Arrows`, `Ctrl+Shift+Arrows`) in standard applications (Word, Notepad, Chrome) now preserves native Devanagari text and clipboard formats without unwanted conversion or corruption.
- **Universal Script & Symbol Protection**: Full protection for Arabic decimals and numbers (`8848.86`, `8516`, `100%`), math symbols, emojis, bullets (`•`, `*`, `-`), and stars (`★`) across all detection paths.
- **Document Language Dominance (>=20% Rule)**: If >=20% of observed words in a document are Unicode Devanagari, the document context is locked to Unicode, preventing English text, numbers, or symbols from ever being falsely identified as Preeti unless explicitly tagged with a legacy font name.
- **Preeti Clause Brackets & 9/0 Key Resolution**: Parenthesized words and legal clauses (e.g. `(s)` -> `(क)`, `(v)` -> `(ख)`, `(lzIff)` -> `(शिक्षा)`, `(!)` -> `(१)`, `9s0` -> `(क)`) accurately preserve outer parentheses instead of turning into digits `९...०` or `ढकण्`, while genuine multi-digit Preeti numbers (e.g. `@)@(` -> `२०२९`, `@)` -> `२०`, `*(` -> `८९`) remain numbers.
- **Startup Guidance & Toggle Reminders**: Clear user notifications on startup and on mode toggle (`NVDA+Ctrl+Shift+Space`) advising users to keep Nepali mode OFF during English typing or system navigation and ON when reading Nepali documents.

## [1.1.3] - 2026-10-06 (Stable Release)

### Added
- **Startup & Toggle Guidance**: Automatic announcement and settings panel tip recommending users keep Nepali mode OFF (`NVDA + Ctrl + Shift + Space`) during English typing, programming, or menu navigation, and toggle it ON when reading Nepali documents.
- **Smart English Number & Symbol Protection**: Numbers like `8848.86`, `8516`, and standalone bullets (`*`, `•`, `-`) are protected from being misidentified as Preeti keys.
- **Ultra-Lightweight Distribution**: Completely removed user-facing OCR and heavy Tesseract data, shrinking package size from 27 MB to 2.99 MB.

## [1.1.2] - 2026-10-06

### Fixed
- **Selective Delta Announcements**: Fixed text selection so `Shift + Arrows` speaks only the newly selected/unselected delta chunk rather than repeating the entire selection from top to bottom.
- **Preeti Typewriter Typo Repairs**: Automatic restoration of `dxj` -> `महत्त्व`, `महवको` -> `महत्त्वको`.
- **Publisher Name**: Updated official publisher name to `Suyog Dhungel`.

## [1.0.0] - 2026-10-05 (Official Initial Release)

### Added
- **Universal Legacy Font Reading**:
  - Full offline support for Preeti, Kantipur, Sagarmatha, Fontasy Himali, and PCS Nepali fonts.
  - Full support for Hindi Kruti Dev fonts (`krutidev010`, `k010`, etc.) with Hindi synthesizer voice switching.
  - Automatic English word and font preservation (Calibri, Arial, Times New Roman, code blocks, URLs, and emails are never falsely converted).
  - Punctuation, parentheses, and bullet symbol preservation (`•`, `●`, `■`, `✓`, `★`, `→`, `–`, `—`).
- **Advanced Devanagari PDF Reconstruction Engine**:
  - Direct TrueType glyph outline and font table reconstruction for broken Devanagari text layers from Microsoft Word ("Save as PDF"), InDesign, Chrome PDFium/HarfBuzz, and LibreOffice.
  - Resolves misplaced short-i (`ि`), reph (`र्`), and split conjuncts in the background.
  - Syllable-accurate character navigation (`Left/Right Arrow`) with mathematical akshara partitioning.
  - Word navigation (`Ctrl + Left/Right Arrow`) through reconstructed Devanagari words.
  - Accurate multi-word text selection (`Shift + Arrows`).
- **eSpeak Devanagari Numeral Pronunciation**:
  - Automatic Nepali language tagging for Devanagari text and numerals.
  - eSpeak pronounces act numbers, section headers, and dates aloud in Nepali (e.g. `२०७५`, `२३`, `१.`).
- **Smart Unicode Clipboard Copy (`Ctrl + C`)**:
  - Copying in browse mode or focus mode converts selected legacy font text or repaired PDF text into clean, standard Unicode Devanagari on the clipboard.
- **Offline OCR (`NVDA + Alt + O`)**:
  - Integrated Tesseract OCR engine for Nepali, Hindi, and English to read scanned documents and image PDFs without internet access.
- **NVDA Menu & Gesture Customization**:
  - NVDA Menu (`NVDA + N`) -> Tools -> Nepali Reader submenu.
  - NVDA Menu (`NVDA + N`) -> Preferences -> Settings -> Nepali Reader panel.
  - NVDA Menu (`NVDA + N`) -> Preferences -> Input gestures -> Nepali Reader category for full shortcut customization.
