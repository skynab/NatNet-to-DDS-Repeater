# GUI translations

This folder holds the text shown in `NatNetToDDSGui.py` and `DDSTestClientGui.py`. There is one JSON file per language:

| File | Language |
|---|---|
| `en.json` | English (the reference: every id must exist here) |
| `zh_CN.json` | Simplified Chinese |

You can edit these files without touching any Python code. Restart the GUI, or pick the language again in the window's **Language** menu, to see your changes.

## Editing a translation

Each line maps a message id to its text:

```json
"bridge.frames_ok": "{fps:.1f} fps，第 {frame} 帧\n已发布 {published} 帧",
```

- **Don't change the id** (the part before the colon).
- **Keep every `{placeholder}` exactly as written**, including any format code such as `{fps:.1f}`. You can move a placeholder within the sentence, but don't rename, translate or remove it.
- `\n` starts a new line. A literal `"` must be written as `\"`.
- Keep product and protocol names in English: Motive, NatNet, DDS, QoS, fps, the topic names (`NatNet_FrameOfMocapData`, `NatNet_RigidBody`) and file names.
- Keys that start with `_` are notes for translators. `_language_name` is the language's own name, as shown in the Language menu.
- Save the file as UTF-8.

If a message is missing or its placeholders don't match, the GUI shows the English text for that message instead of crashing.

## Checking your work

From the project folder, run:

```bash
python -m natnet_dds.i18n
```

The check compares every file with `en.json` and reports ids that are missing, ids that aren't in `en.json`, and placeholder mismatches. It prints `OK` for each file that's complete.

## Adding a language

Copy `en.json` to a new file named after the language code, for example `ja.json`. Set `_language_name` to the language's own name (`日本語`), then translate the values. The new language appears in both windows' Language menus.

## Not translated

The **Log** pane shows messages from the bridge, the NatNet SDK and the DDS libraries. They are the same messages the command-line programs print, so they stay in English.
