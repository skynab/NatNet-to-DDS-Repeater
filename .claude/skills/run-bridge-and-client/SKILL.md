---
name: run-bridge-and-client
description: Launch (or restart) the NatNet-to-DDS bridge and the DDS test client in this repo, as GUI windows by default or headless on the command line, optionally with the mock Motive server. Use when asked to run, start, restart or relaunch the bridge, the client, or both.
---

# Run the bridge and the test client

The two apps are `NatNetToDDSGui.py` (bridge) and `DDSTestClientGui.py` (test client).
Their headless equivalents are `NatNetToDDS.py` and `DDSTestClient.py`.
Unless the user asks for the command line, launch the **GUIs**.

## 1. Check the environment

- Always use the repo's venv interpreter, `.venv/bin/python` (`.venv\Scripts\python` on Windows).
- If `.venv` is missing, create it, then install the requirements:
  `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
- On this Mac, RTI Connext can't create a participant (shared-memory limits, see the README).
  The default `--dds auto` therefore falls back to Cyclone DDS. That is expected, not an error.

## 2. Stop old instances first

Running a second copy of either window splits the settings file and confuses the status lights.

1. Find old instances with `mcp__terminal__list_terminal_tabs`. Look for tabs titled `bridge`, `client` and `mock`.
2. Cross-check with this command:
   ```bash
   ps -o pid,etime,command -ax | grep -E 'NatNetToDDS|DDSTestClient|MockNatNetServer' | grep -v grep
   ```
3. Before stopping anything, look at the bridge tab with `mcp__terminal__read_terminal`.
   If it shows a live connection (`[natnet] connected to …` with no `[bridge] stopped` after it),
   tell the user the restart will end that session.
4. Stop the old instances:
   - **GUIs:** Tk windows often ignore Ctrl-C, so `kill <pid>` the Python processes found above.
     The shells in the `bridge` and `client` tabs then return to their prompt.
   - **Command-line runs:** `mcp__terminal__stop_terminal_tab` (Ctrl-C) is enough.

## 3. Launch

Each app runs in its own Terminal-panel tab (`mcp__terminal__run_in_terminal`), so the user can see its output and stop it.
Use `cwd` = the repo root and the tab titles shown below. If a `bridge` or `client` tab from earlier is back at its prompt, reuse it by passing its `tab_id`.

**GUIs (default):**

| Tab | Command |
|---|---|
| `bridge` | `.venv/bin/python NatNetToDDSGui.py` |
| `client` | `.venv/bin/python DDSTestClientGui.py` |

The windows open idle. The user presses **Start bridge** and **Start** themselves, using the settings each window remembers in `~/.natnet_dds_bridge_gui.json` and `~/.natnet_dds_client_gui.json`.

To test without Motive, the bridge window's **Start mock Motive** button starts the mock server.
For that, the bridge's server and local interface must be `127.0.0.1`.

**Command line (when asked, or for an unattended check):**

| Tab | Command |
|---|---|
| `mock` (only without Motive) | `.venv/bin/python MockNatNetServer.py` |
| `bridge` | `.venv/bin/python NatNetToDDS.py` |
| `client` | `.venv/bin/python DDSTestClient.py --verify-mock` |

- Drop `--verify-mock` when the source is real Motive.
- For real Motive on another machine, pass these to the bridge: `--server <motive ip> --client <this pc ip>`, plus `--unicast` if Motive streams unicast.
- Keep the same `--domain N` on both ends.
- Useful extras:
  - `--stats-window N` sets the metrics window (both apps).
  - `MockNatNetServer.py --drop-every 60` makes the mock skip frames, to exercise the loss metrics.
  - `--fps 240` changes the mock's frame rate.

**One-shot end-to-end test:** `.venv/bin/python run_loopback_test.py` starts mock → bridge → client, checks the data, and exits. Run it with Bash, not in a tab.

## 4. Verify

- Wait about 3 s, then `mcp__terminal__read_terminal` each tab with `wait_for_output_ms`. Check for tracebacks.
- GUIs print nothing at startup, so for them confirm the processes are alive with the `ps` command from step 2.
- Command-line runs print status every second. Expect `[natnet] connected to …` and then frame/metric lines in the bridge tab.
  Expect `[dds] frames … missed 0` in the client tab, and `PASS` with `--verify-mock`.
- Screenshots can't capture the Tk windows from here; they come out as the wallpaper.
  Don't claim anything about the on-screen layout.

## 5. Report

- Say which mode was launched and which tabs to open, linking each tab as `[bridge](#terminal/<tab_id>)`.
- Say whether an earlier session was stopped.
- Say what the user still has to press: **Start mock Motive** if there's no Motive, then **Start bridge**, then **Start** in the client.
