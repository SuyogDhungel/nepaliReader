# Changelog

All notable changes to the **Nepali Reader** NVDA add-on are documented here.

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
- **Nepal ko Sambidhan & Genitive 'को' Resolution**: Corrected genitive vibhakti postposition `को` across titles and clauses (e.g. `नेपालको संविधान`), preventing mispronunciation as "ka" caused by unparsed `ा]` matra residue.
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
- **Startup Guidance & Toggle Reminders**: Clear user notifications on startup and on mode toggle (`NVDA+Alt+N`) advising users to keep Nepali mode OFF during English typing or system navigation and ON when reading Nepali documents.

## [1.1.3] - 2026-10-06 (Stable Release)

### Added
- **Startup & Toggle Guidance**: Automatic announcement and settings panel tip recommending users keep Nepali mode OFF (`NVDA + Alt + N`) during English typing, programming, or menu navigation, and toggle it ON when reading Nepali text or PDFs.
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
