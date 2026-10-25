# Changelog

What changed for the user in each release. The full text of each release, in English and
Russian, is on the [releases page](https://github.com/ALEXalesha/SortDownloads/releases).

## 4.2.0 - 2026-09-25 - The window opens where it was closed, at the same size

Both windows write their place to `window.json` next to `config.json`: the PyQt window under `qt`, the old Tkinter one (`--tk`) under `tk`, and neither wipes the other's key. If that monitor is gone or the title bar would land off every screen, the window opens at its default size instead; a broken file does the same. Tkinter has no `restoreGeometry`, so its rule is a port of the `window-state.js` used by the calculators and Paint Pro, and a test checks the Python answers against `window-state.js` itself on a thousand random inputs.

The files now have Latin names with the version: GitHub dropped the Cyrillic from the names, so 4.1.0 shipped as `-Setup.exe` and `-portable.zip`.

674 tests green.

## 4.1.0 - 2026-09-23

First public release. The interface is in Russian; the README explains what the window shows.

### New in 4.1: rules from the window

- **⚙ Правила** (Rules): add, rename and remove categories, add and remove keywords, without touching JSON.
- While you type a keyword, the dialog counts how many files of the current plan it would take and from which categories.
- Right click a file in the plan to always put it into a category.
- Edits live in `my_rules.json` on top of the shipped `rules.json`, so updates still deliver new categories and your edits survive them.

### Also fixed

- The installer no longer ships the author's own `config.json` and `overrides.json`. A first start without settings is normal now: your Downloads folder, 3D export off, and the window writes `config.json` itself.

### Checked before release

656 tests including hypothesis properties for the rules editor, and a manual run of the built exe: a category and a keyword added from the dialog, the plan rebuilt, a right-click rule, and the edits still in place after a restart. That run found one bug (Enter in the keyword field also pressed "add category"), fixed before this build.
