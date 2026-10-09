# Nepali Reader for NVDA

[![Download Add-on](https://img.shields.io/badge/Download-nepaliReader--1.1.4.nvda--addon-brightgreen?style=for-the-badge&logo=nvda)](https://github.com/SuyogDhungel/nepaliReader/releases/download/v1.1.4/nepaliReader-1.1.4.nvda-addon)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](LICENSE)
[![NVDA Compatibility](https://img.shields.io/badge/NVDA-2024.1%20to%202026.2-purple.svg)](https://www.nvaccess.org/)

**Nepali Reader** is a free, open-source NVDA screen reader add-on created to solve the long-standing Devanagari reading issues faced by blind and visually impaired computer users in Nepal.

> [!TIP]
> **Recommendation**: Keep Nepali Mode OFF (`NVDA + Alt + N`) when working in English documents, browsing English websites, or programming. Toggle it ON when reading Nepali documents, gazettes, or PDFs.

---

## 📌 Why This Add-on Was Created

Screen reader users in Nepal regularly encounter two major barriers when reading documents:

1. **Legacy Devanagari Fonts**: Official government acts, gazettes, legal notices, newspapers, and school materials are frequently typed in legacy fonts like **Preeti**, **Kantipur**, **Sagarmatha**, **Fontasy Himali**, and **PCS Nepali**. Screen readers see these fonts as plain English characters, reading meaningless gibberish (such as reading `"g]kfn"` instead of `"नेपाल"`).
2. **Damaged PDF Text Layers**: When government offices and organizations export documents to PDF from Microsoft Word ("Save as PDF"), InDesign, or web print tools, the underlying Devanagari Unicode text layer becomes heavily jumbled. Matras appear out of order, letters are missing, and conjuncts are broken.
3. **Silent Numbers in eSpeak**: Screen reader synthesizers like eSpeak often skip or remain silent on Devanagari numerals (`०, १, २, ३, ४, ५, ६, ७, ८, ९`), making section numbers, act years, and dates unreadable.

**Nepali Reader** solves all of these problems automatically and completely **offline**. It reconstructs the text directly from the font shapes and tables inside the document so NVDA speaks natural, accurate Devanagari without any internet connection.

---

## 📥 How to Download and Install

1. Download the add-on file:
   👉 [**Click here to download nepaliReader-1.1.4.nvda-addon**](https://github.com/SuyogDhungel/nepaliReader/releases/download/v1.1.4/nepaliReader-1.1.4.nvda-addon)
2. Once downloaded, open your **Downloads** folder and press **Enter** on `nepaliReader-1.1.4.nvda-addon`.
3. NVDA will ask: *"Are you sure you want to install this add-on?"* — Press **Yes** (`Alt + Y`).
4. When prompted to restart NVDA, select **Yes**.
5. That is all! Nepali Reader activates automatically upon startup.

*Alternative installation method*: Open the **NVDA Menu (`NVDA + N`) $\to$ Tools $\to$ Add-on Store**, switch to the **Installed add-ons** tab, choose **Install from external file...**, select the downloaded file, and restart NVDA.

---

## 🧭 How to Use This Tool

### 1. Using via the NVDA Menu

You can control all features directly through the NVDA menu using your keyboard:

* **Toggle Nepali Mode on / off**:
  1. Press **`NVDA + N`** to open the NVDA Menu.
  2. Press **`T`** to open the **Tools** submenu.
  3. Navigate to **Nepali Reader** and press **Enter**.
  4. Check or uncheck **Nepali mode** to turn the add-on on or off.

* **Convert Highlighted Text or Clipboard**:
  1. If you are in an application where text is not reading, select the text (or copy it to your clipboard).
  2. Press **`NVDA + N` $\to$ Tools $\to$ Nepali Reader $\to$ Convert selected text or clipboard**.
  3. NVDA will convert the text to Unicode, copy the clean text to your clipboard, and read it aloud immediately.

* **Add-on Settings**:
  1. Press **`NVDA + N` $\to$ Preferences $\to$ Settings**.
  2. In the categories list, press **`N`** until you reach **Nepali Reader**.
  3. Here you can configure legacy font detection, switch languages automatically, or adjust repair settings.

---

### 2. Default Keyboard Shortcuts

| Shortcut | What It Does |
|---|---|
| **`NVDA + Alt + N`** *(or `NVDA + Ctrl + Shift + Space`)* | **Toggle Nepali Mode**: Quickly turns reading conversion on or off. NVDA will announce *"Nepali mode on"* or *"Nepali mode off"*. `NVDA + Alt + N` is recommended for laptop users. |
| **`Ctrl + C`** | **Smart Copy**: While Nepali mode is active, copying selected text automatically places clean, standard Unicode Devanagari onto your clipboard (ready to paste into Word, Facebook, or messaging apps). |
| **`NVDA + Alt + U`** | **Convert and Read**: Converts whatever text is currently selected (or on the clipboard) to Unicode and speaks it aloud. |
| **`NVDA + Alt + P`** | **Legacy Font Mode**: Cycles font conversion between *Automatic* (default), *Always Convert*, and *Off*. |
| **`NVDA + Alt + Shift + P`** | **Default Font Family**: Switches the default legacy font between Preeti, Kantipur, Sagarmatha, Himali, and PCS. |

---

### 3. How to Create or Customize Your Own Shortcuts

If any shortcut conflicts with another add-on or if you prefer different keys, you can assign your own:

1. Press **`NVDA + N`** to open the NVDA Menu.
2. Go to **Preferences** and press Enter on **Input gestures...**.
3. In the tree view, press **`N`** until you find the **Nepali Reader** category, then press **Right Arrow** to expand it.
4. You will see a list of actions:
   * *Toggle Nepali mode*
   * *Convert the selected text or the clipboard to Unicode*
   * *Legacy font reading: automatic, always convert, off*
   * *Default legacy font family*
5. Select the action you wish to change.
6. Press **`Alt + A`** (or Tab to the **Add** button and press Enter).
7. Press the exact key combination you want to use on your keyboard (for example, `NVDA + Shift + N`).
8. Select whether to use this shortcut for `all layouts` or your current keyboard layout and press **Enter**.
9. Tab to the **OK** button and press Enter to save your new shortcut.

---

## 📑 Reading PDFs and Documents

* **Up / Down Arrow**: Reads line by line. Scrambled government PDFs are rebuilt into clear Nepali sentences.
* **Left / Right Arrow**: Moves character by character. Accurately speaks individual characters and vowel signs without repetition.
* **Ctrl + Left / Right Arrow**: Moves word by word through real Devanagari words.
* **Shift + Arrows**: Selects text accurately without broken characters.
* **Numbers & Dates**: Dates like `२०७५` and numbers like `१.`, `(१)`, `२३` are announced in spoken Nepali via eSpeak.
* **MultiLang & Multi-Voice TTS Support**: Seamlessly integrates with the **MultiLang** virtual synthesizer add-on. If MultiLang is active, Nepali Reader ensures Devanagari text is correctly recognized as Nepali (`ne`) rather than forced to Hindi (`hi`), and automatically routes speech to installed Nepali TTS voices (such as **Hear2Read Indic Voices** with Google Nepali voice or **eSpeak NG**) across Word documents, PDFs, and web browsers.

---

## 📜 Changelog

### Version 1.1.5 (Current Release)
* **Seamless MultiLang Add-on Integration**: Full automatic integration with the popular MultiLang virtual synthesizer add-on. Ensures Devanagari text is recognized as Nepali (`ne`) rather than forced to Hindi (`hi`).
* **Supporting TTS Voice Discovery**: Automatically resolves and activates the best available Nepali voice across installed synthesizers—including Hear2Read Indic Voices (`Hear2ReadNG` with Google Nepali neural voice) and eSpeak NG (`ne`)—without requiring manual NVDA configuration profiles.
* **Microsoft Word Proofing Language Override**: Overrides Word's default `hi-IN` language tagging on Devanagari paragraphs whenever the vocabulary is identified as Nepali, ensuring MultiLang and NVDA switch to the Nepali voice rather than Hindi.
* **Preeti Bracket Matra Parsing**: Fixed Preeti keyboard typography where `]` (e-kar / o-kar), `}` (ai-kar / au-kar), `[` (ri-kar), and `{` (reph) were stripped as punctuation brackets, eliminating corrupted words like `रहेका] छ` -> `रहेको छ`, `शिक्षाल]` -> `शिक्षाले`, `यसका] पुर}` -> `यसको पुरै`, `कुन}` -> `कुनै`, `पाइन]` -> `पाइने`, `पहिला]` -> `पहिलो`, `हाम्रा]` -> `हाम्रो`.
* **Himali Downward U-kar (`\xac` / `¬`)**: Added missing `\xac` Alt+0172 character to `PREETI_MAP`, fixing words like `स¬झावहरू` -> `सुझावहरू`.
* **Preeti/Himali `क्र` Modifier Conjuncts**: Extended glyph modifier resolution for `व` + `्र` + modifier `m`, restoring `पाठ्यव्रम` -> `पाठ्यक्रम`, `कार्यव्रम` -> `कार्यक्रम`, `व्रियाकलाप` -> `क्रियाकलाप`, `प्रव्रिया` -> `प्रक्रिया`.
* **Number Preservation in MultiLang**: Prevented MultiLang from dropping Devanagari numerals (`०-९`) and numbers attached to Nepali clauses into English speech.

### Version 1.1.4
* **Double Character Reading Elimination**: Character navigation (`Left/Right Arrow`) speaks individual characters and vowel signs cleanly without repeating syllables twice.
* **Preeti Clause Brackets & 9/0 Key Resolution**: Parenthesized words and legal clauses (e.g. `(s)` -> `(क)`, `(v)` -> `(ख)`, `(lzIff)` -> `(शिक्षा)`, `(!)` -> `(१)`, `9s0` -> `(क)`) accurately preserve outer parentheses rather than turning into digits `९...०` or `ढकण्`, while genuine multi-digit Preeti numbers (`@)@(` -> `२०२९`, `@)` -> `२०`) remain numbers.
* **Native Unicode Selection & Copying**: Preserves native Devanagari text and clipboard formats on `Ctrl+C`, `Ctrl+A`, `Shift+Arrows`, and `Ctrl+Shift+Arrows` in standard applications (Word, Notepad, Chrome) without unintended conversion.
* **Universal Script & Symbol Protection**: Arabic numbers and decimals (`8848.86`, `8516`, `100%`), math symbols, emojis, bullets (`•`, `*`, `-`), and stars (`★`) are strictly protected from false legacy conversion.
* **Document Language Dominance (>=20% Rule)**: If >=20% of observed words in a document are Unicode Devanagari, the context is locked to Unicode so English text, numbers, and symbols are never converted as Preeti unless explicitly tagged by font name.
* **Startup Guidance & Toggle Reminders**: Clear user notifications on startup and on toggle (`NVDA+Alt+N`) advising users to keep Nepali mode OFF during English typing or system menus and ON when reading Nepali documents.

### Version 1.1.3
* Startup announcement and settings panel tip recommending users keep Nepali mode OFF (`NVDA + Alt + N`) during English typing or system menus and ON when reading Nepali documents.
* Streamlined distribution package size to 2.99 MB.

### Version 1.1.2
* **Selective Delta Announcements**: Fixed selection speech announcement so ONLY newly selected/unselected text is spoken instead of repeating the entire selection from top to bottom.
* **Typo Repairs & Normalization**: Added automatic correction for Preeti typewriter typos (`dxj` -> `महत्त्व`, `महवको` -> `महत्त्वको`, `महवराख्ने` -> `महत्त्व राख्ने`).
* **Line-Wrap Artifact Removal**: Removed trailing multi-space artifacts and orphan hyphenated syllables at PDF line breaks.
* **Laptop Rollover Fix**: Full support for `NVDA + Alt + N` as a conflict-free toggle gesture for laptop keyboard layouts.
* **NVDA Store Compatibility**: Fully validated for stable NVDA 2024.1 through 2026.2.

### Version 1.0.0 (Official Initial Release)
* Universal automatic conversion for Preeti, Kantipur, Sagarmatha, Fontasy Himali, and PCS Nepali fonts.
* Deep TrueType glyph reconstruction for broken text-based Devanagari PDFs from Word, InDesign, Chrome, and LibreOffice.
* Automatic Nepali language tagging for eSpeak Devanagari numeral pronunciation.
* Smart clipboard copy (`Ctrl + C`) that converts legacy and PDF text directly to standard Unicode.
* Full NVDA menu and custom input gesture integration.

---

## ⚖️ License

Distributed under the **GNU General Public License v2.0 (GPL-2.0)**. See [LICENSE](LICENSE) for details.

## 🤝 Project & Support
* **Authors & Maintainers**: Suyog Dhungel (<dhungelsuyog13@gmail.com>), Roshan Gautam (<mr.pawittra@gmail.com>)
* **Project**: Nepali Reader for NVDA
* **GitHub Repository**: [https://github.com/SuyogDhungel/nepaliReader](https://github.com/SuyogDhungel/nepaliReader)
* **Feedback & Issues**: Please report issues or suggest improvements by opening an [Issue](https://github.com/SuyogDhungel/nepaliReader/issues) on GitHub.
* **Tags**: `nepali`, `nvda`, `nvda-addon`, `preeti-font`, `screen-reader`, `accessibility`, `devanagari`, `kantipur-font`
