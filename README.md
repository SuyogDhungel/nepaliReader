# Nepali Reader for NVDA

[![Download Add-on](https://img.shields.io/badge/Download-nepaliReader--2.2.1.nvda--addon-brightgreen?style=for-the-badge)](https://github.com/SuyogDhungel/nepaliReader/releases/download/v2.2.1/nepaliReader-2.2.1.nvda-addon)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](LICENSE)
[![NVDA Compatibility](https://img.shields.io/badge/NVDA-2024.1%20to%202026.2-purple.svg)](https://www.nvaccess.org/)

**Nepali Reader** is a free, open-source add-on for the NVDA screen reader. It makes NVDA read Nepali documents correctly: Preeti and other old Nepali fonts, and PDFs whose Nepali text comes out jumbled. Everything works offline.

**Latest version: 2.2.1** · [Download](https://github.com/SuyogDhungel/nepaliReader/releases/download/v2.2.1/nepaliReader-2.2.1.nvda-addon) · [What changed](CHANGELOG.md)

---

## Why this add-on exists

Blind and visually impaired computer users in Nepal meet three problems in everyday documents:

1. **Old Nepali fonts.** Acts, gazettes, notices, newspapers and school books are often typed in **Preeti**, **Kantipur**, **Sagarmatha**, **Fontasy Himali**, **PCS Nepali** or (for Hindi) **Kruti Dev**. The computer stores these as English letters, so NVDA reads `g]kfn` instead of `नेपाल`.
2. **Damaged PDF text.** PDFs saved from Microsoft Word, InDesign or web tools store their Nepali text wrongly: vowel signs out of place, letters missing, conjuncts broken (`शल्ुक` for `शुल्क`).
3. **Silent numbers.** Some voices skip Devanagari digits (`०–९`), so dates and section numbers go unheard.

Nepali Reader fixes all three. For a PDF it reads the PDF file itself, the letters the page actually draws, so NVDA says what is printed.

---

## What's new in 2.2.1

* **Faster in PDFs:** arrow keys, selecting and the other reading keys respond quicker, also on long PDFs, and long PDFs no longer make NVDA pause for a few seconds.
* **PDFs that store their text in an unusual order** now read as printed, in any font.

## What's new in 2.2.0

* **Highly accurate reading.** Many parts of how the add-on reads have been changed, so NVDA reads Nepali documents as they are written: PDFs, Preeti and other legacy fonts, Word and web pages.
* **Reading by line, word and character, selecting and copying** all give the same accurate text.
* **English stays English**, also in code editors and terminals.
* **Updating without the Add-on Store:** *Check for updates* shows everything that changed since your version, then downloads, checks and installs the new version, and offers to restart NVDA.

Details: [CHANGELOG.md](CHANGELOG.md).

---

## Download and install

1. Download **[nepaliReader-2.2.1.nvda-addon](https://github.com/SuyogDhungel/nepaliReader/releases/download/v2.2.1/nepaliReader-2.2.1.nvda-addon)** (from the [Releases page](https://github.com/SuyogDhungel/nepaliReader/releases)).
2. Open your **Downloads** folder and press **Enter** on the file.
3. NVDA asks whether to install the add-on (or to update it, if an older version is installed). Press **Yes** (`Alt+Y`).
4. When NVDA offers to restart, choose **Yes**.

Nepali Reader is on from the start. Nothing else needs setting up.

*Other way:* NVDA menu (`NVDA+N`) → Tools → Add-on Store → *Install from external file…*, choose the downloaded file, then restart NVDA.

---

## Updating

**From version 2.2.0 on:** NVDA menu (`NVDA+N`) → Tools → Nepali Reader → **Check for updates…**. The add-on also checks once a day. You can turn that off in Settings → Nepali Reader → *Automatically check for updates from GitHub*.

When a new version is out, a window opens:

* a text box with **everything that changed since your version**. Read it line by line with the arrow keys;
* **Update now** downloads the new version. NVDA says the progress at 25, 50 and 75%. The download is checked: a download that was cut short, an error page or a wrong file is never installed;
* NVDA then asks to update the add-on and offers to restart. The new version starts after the restart;
* **Later** closes the window.

Only one check or download runs at a time, and all of it happens in the background: NVDA keeps reading while the update downloads.

**From an older version:**

| You have | How to get the latest version |
|---|---|
| 1.1.6, 1.1.7, 2.0 or 2.1.0 | Your version's own updater offers the latest version (NVDA menu → Tools → Nepali Reader → Check for updates, or the daily check). Answer **Yes**. When it is installed, **restart NVDA**. |
| 2.0.1 or 2.0.2 (also the Add-on Store version), or 1.1.5 and older | These versions have no updater. Download the file above and install it. Your settings are kept. |

After updating, each PDF is read again once, in the background, the first time you open it. Reading starts at once while that happens.

---

## How to use it

### Keys

| Key | What it does |
|---|---|
| **`NVDA+Ctrl+Shift+Space`** | Nepali mode on or off. NVDA says *"Nepali mode on"* or *"Nepali mode off"*. Off is completely off: nothing is hooked into NVDA and no work runs. |
| **`NVDA+Ctrl+L`** | Opens the Nepali Reader settings. |
| **`Ctrl+C`** | Works as usual. In Nepali mode the copied text is correct Unicode Nepali (Preeti converted, PDF text rebuilt). |

The other commands (convert selected text, legacy font mode, default legacy font) have no key by default. Use the menu, or give them a key: NVDA menu → Preferences → Input gestures → Nepali Reader → choose the command → **Add** → press your keys → OK.

> [!TIP]
> Keep Nepali mode **off** (`NVDA+Ctrl+Shift+Space`) when you work in English documents, browse English websites or write code. Turn it **on** for Nepali documents, gazettes and PDFs.

### Menu

NVDA menu (`NVDA+N`) → Tools → **Nepali Reader**:

* **Nepali mode**: on or off.
* **Convert selected text or clipboard**: converts the selection (or the clipboard) to Unicode, copies it and reads it.
* **Check for updates…**
* **Settings…**

### Settings

NVDA menu → Preferences → Settings → **Nepali Reader** (or `NVDA+Ctrl+L`):

* Nepali mode, legacy font reading (automatic, always convert, off) and the default legacy font
* read the PDF file itself for the exact text (on by default)
* repair jumbled Unicode Devanagari from PDFs
* mark converted text as Nepali so the voice can switch language
* table header announcements in PDF tables
* automatic update check

---

## Reading PDFs and documents

* **Up / Down Arrow** read line by line, as printed.
* **Left / Right Arrow** move by character. Each key says its letter or vowel sign once. In a Preeti PDF, a key that changes the sign before it says the new sign (ा then ो).
* **Ctrl+Left / Right Arrow** move by whole Nepali words.
* **Shift+Arrows** select. NVDA says exactly what is selected, in Nepali.
* **Tables, headings and formatting**: in Chrome, Edge and Brave the add-on gives NVDA the PDF's tables, headings, bold, italic, underline, alignment and indentation at the right words. `Ctrl+Alt+Arrows` move by table cell, `T` jumps to the next table, `H` to the next heading. A copied table pastes into Word or Excel as a real table.
* **Works in:** Chrome, Edge, Brave and Firefox (also Chrome's "PDF Viewer" extension), Adobe Reader, Foxit, SumatraPDF, Word, Notepad, web pages and e-mail.
* **Scanned PDFs** (pictures of pages) have no text to read. Use an OCR add-on for those.
* **Numbers and dates** like `२०७५`, `१.`, `(१)` are spoken in Nepali.
* **Voices:** converted text is marked as Nepali, so NVDA can switch to a Nepali voice: eSpeak NG (built in), Hear2Read, or a voice through the **MultiLang** add-on. Keep *Automatic language switching* on in NVDA's voice settings.

The first time you open a long PDF, the add-on reads the file in the background. A small notice takes under a second; a 430-page book takes about a minute. You can read straight away. The work pauses whenever you press a key, so NVDA stays quick. The result is saved, so the next time is instant.

---

## Troubleshooting

* **Something reads wrong or NVDA feels slow:** press `NVDA+Ctrl+Shift+Space` to switch Nepali mode off. NVDA is then exactly as without the add-on.
* **Reporting a problem:** open an [Issue](https://github.com/SuyogDhungel/nepaliReader/issues) with the document (or a page of it) and the add-on's log, `%APPDATA%\nvda\nepaliReader\diag.log`. The log notes what was read and what the add-on made of it.
* **A PDF in a browser is not read exactly:** the add-on needs the PDF file. For a web PDF it downloads the file once; a copy in Downloads, Desktop or Documents is used too.
* **Update check says it cannot connect:** check your internet connection and try again later. Nothing is changed until a whole, checked download is ready.

---

## For developers

* Source: `source/addon` (the add-on), `source/tests` (tests). Build with `python build.py`.
* Tests run without NVDA: `python tests/<test>.py` from the `source` folder. Some read real documents when a folder is given: `NEPALI_TEST_PDFS`, `NEPALI_TEST_LAWS`, `NEPALI_TEST_BOOK`.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for every version.

## License

GNU General Public License v2.0 (GPL-2.0). See [LICENSE](LICENSE).

## Project and support

* **Creator and author:** Suyog Dhungel
* **Contributor:** Roshan Gautam
* **Repository:** [github.com/SuyogDhungel/nepaliReader](https://github.com/SuyogDhungel/nepaliReader)
* **Feedback and issues:** [open an Issue](https://github.com/SuyogDhungel/nepaliReader/issues)
* **Credits:** Kruti Dev rules from kru2uni / krutidev-unicode (ISC). Preeti tables cross-checked with npttf2utf. Nepali word list: Nepali Hunspell dictionary, Madan Puraskar Pustakalaya (LGPL 2.1). Nepali word counts: nlp-doko news corpus. English word list: Webster's Second International (public domain).
* **Tags:** `nepali`, `nvda`, `nvda-addon`, `preeti-font`, `screen-reader`, `accessibility`, `devanagari`, `kantipur-font`
