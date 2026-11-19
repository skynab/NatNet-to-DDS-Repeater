# NatNet to DDS

A Python sample that receives OptiTrack Motive data with the NatNet SDK 4.5 Python client and republishes it on DDS ([RTI Connext DDS](https://www.rti.com/products/dds-standard) or any other DDS-RTPS implementation). It comes with a DDS test client that checks the data arrives intact. Everything is plain Python, so it runs on Windows, macOS and Linux.

Bridge

<img width="810" height="754" alt="image" src="https://github.com/user-attachments/assets/a0da84d8-5e5f-4bc5-8c22-ddd11291acbe" />

Client

<img width="786" height="696" alt="image" src="https://github.com/user-attachments/assets/98aa2164-b0e8-4c09-a098-ce4afe4f9d42" />


```
Motive ──NatNet (UDP)──> NatNetToDDS.py ──DDS (RTPS)──> DDSTestClient.py
                                                  └──> any DDS app (C++, Java, ROS 2, …)
```

## Files

| File | What it is |
|---|---|
| `NatNetToDDS.py` | The bridge. It is based on the SDK's `PythonSample.py` and uses the SDK `NatNetClient`. |
| `DDSTestClient.py` | A DDS subscriber. It prints the data and reports data rate, packet loss, latency, source timestamps and optional value checks. |
| `MockNatNetServer.py` | A simulated Motive server (NatNet 4.5) that streams a fixed synthetic scene, so you can test without cameras. |
| `run_loopback_test.py` | One-command end-to-end test: mock → bridge → DDS → test client. |
| `NatNetToDDSGui.py` | Window for the bridge: connection settings, status lights for each hop, live rigid body poses, and a button that starts the mock server. |
| `DDSTestClientGui.py` | Window for the test client: DDS settings, status lights, the latest frame and rigid body poses, and optional mock verification. |
| `idl/NatNetDDS.idl` | The DDS data model. Use it with `rtiddsgen` to build consumers in other languages. |
| `natnet_dds/` | DDS type definitions (RTI and Cyclone), a small backend wrapper, rolling stream metrics (`metrics.py`), and shared GUI and translation code. |
| `locales/` | GUI translations, one JSON file per language (`en.json`, `zh_CN.json`). |
| `natnet_sdk/` | `NatNetClient.py`, `MoCapData.py`, `DataDescriptions.py` and `PythonSample.py`, copied unmodified from `NatNetSDK/Samples/PythonClient` (SDK 4.5.1). |

## Setup

Python 3.8+.

```bash
python -m venv .venv
```

Activate the venv (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere), then:

```bash
pip install -r requirements.txt
```

### Choosing the DDS implementation (`--dds`)

- **`rti`**: RTI Connext DDS (`pip install rti.connext`). It needs an RTI license at runtime. Set `RTI_LICENSE_FILE=/path/to/rti_license.dat` or put `rti_license.dat` in the working directory. You can get a free evaluation license at https://www.rti.com/free-trial.
- **`cyclone`**: Eclipse Cyclone DDS (`pip install cyclonedds`). No license is needed.
- **`auto`** (default): uses RTI if it can create a participant. Otherwise it prints why and falls back to Cyclone.

Both implementations use the standard DDS-RTPS wire protocol and the same `@final` types. Their XCDR encodings are byte-identical (verified by serializing the same frame with both libraries), so a Cyclone bridge can feed RTI subscribers and the reverse. Both ends must be on the same DDS domain.

## Running with Motive

1. In Motive, open **Streaming** and enable **Broadcast Frame Data**. Note the **Local Interface** IP and the **Transmission Type** (Multicast is the default).
2. Start the bridge:

   ```bash
   python NatNetToDDS.py
   ```

   To reach Motive on another machine (`--client` is this PC's IP on the Motive network):

   ```bash
   python NatNetToDDS.py --server 192.168.1.10 --client 192.168.1.20
   ```

   Add `--unicast` if Motive's Transmission Type is Unicast. Use `--domain N` to pick the DDS domain.
3. In another terminal (on any machine on the DDS network), start the test client:

   ```bash
   python DDSTestClient.py
   ```

   It prints a line like this every second, followed by the latest frame and each rigid body's pose:

   ```
   [dds] frames 242 (120.2 fps)  missed 0  rigid body samples 726  publishers: frame 1, rigid body 1
   ```

   `missed` counts gaps in Motive frame numbers. Under it are one metrics line per topic and the latest frame's source timestamps (see [Metrics](#metrics)). Run `python DDSTestClient.py --help` for options (`--duration`, `--quiet`, `--stats-window`, …).

## Metrics

Both programs, and both windows, report the following. Rate, interval, packet loss and latency are computed over a rolling window, 10 s by default (`--stats-window N`, or **Metrics window** in the GUI).

| Metric | Bridge (NatNet input) | Test client (per DDS topic) |
|---|---|---|
| **Data rate** | Frames per second arriving from Motive, and the rate according to Motive's own frame timestamps ("at source") | Samples per second arriving over DDS, and the source rate |
| **Arrival interval** | Mean, standard deviation and max time between frames (jitter) | Same, measured at the client |
| **Packet loss** | Gaps in Motive frame numbers in the window (with %), since start, and out-of-order frames. Loss here happened between Motive and the bridge. | Same. On `NatNet_RigidBody`, gaps are counted per rigid body, so one lost frame with 3 bodies counts 3. In split mode they are counted per topic, so it counts 6. Loss seen here but not on the bridge happened in DDS. |
| **Latency** | *Motive latency:* camera mid-exposure → Motive transmit, from Motive's hardware clock. *Bridge processing:* NatNet packet received → DDS write finished. | DDS source timestamp → sample taken by the client. It includes up to one 5 ms polling interval of the client, and it is only meaningful when the bridge and client clocks are synchronized (same machine, or NTP/PTP). |
| **Source timestamps** | Motive's frame timestamp (`t`, seconds since Motive started), the mid-exposure and transmit stamps (ticks), Motive's clock frequency, and the DDS source timestamp | The DDS source timestamp of the latest sample on each topic, and Motive's timestamps carried in the sample |

**DDS source timestamp:** the bridge writes every sample with its DDS source timestamp set to the moment the NatNet packet arrived, as wall-clock UTC. All samples made from one Motive frame (the frame sample and each rigid body) share the same source timestamp. DDS applications read it from `SampleInfo.source_timestamp`. The DDS types themselves are unchanged.

**Motive's clock frequency** comes from the server info Motive sends when the bridge connects. The SDK's Python client skips that field, so the bridge reads it itself. Without it, the Motive latency shows `—`. The hardware stamps are zero when Motive isn't live, for example during playback, and then no Motive latency is shown.

To see the loss reporting work without cameras, make the mock server skip frames: `python MockNatNetServer.py --drop-every 60` drops 1 frame in 60 (1.67%).

## GUI

If you'd rather not use the command line, both programs have a small window. They use Tkinter, which ships with Python, so there's nothing extra to install. (On Linux you may need your distribution's `python3-tk` package.)

```bash
python NatNetToDDSGui.py
```

```bash
python DDSTestClientGui.py
```

Fill in the settings and press **Start**. Each window has four status lights, one for each hop the data takes. The first light that isn't green tells you where the data stops:

| Bridge window | Test client window |
|---|---|
| 1. NatNet connection: Motive answered the handshake | 1. DDS participant: DDS started |
| 2. Incoming frames: frames are arriving, with their rate | 2. Matched publishers: the bridge was discovered on this domain |
| 3. DDS publisher: the DDS writers were created | 3. Data flow: samples are arriving, with their rate |
| 4. DDS subscribers: how many readers matched each topic | 4. Integrity: missed frames, or PASS/FAIL with **Verify against mock** |

Below the lights, a **Metrics** panel shows the [metrics](#metrics) described above. The test client shows one column per topic.

Click a section's title (▾) to collapse it to a single line, and click it again (▸) to expand it. The other sections take the freed space, and each window remembers which sections were collapsed.

When a light is amber or red, its text suggests what to check, for example the transmission type or the DDS domain. Below the lights, each window shows the live rigid body poses and a log. At the bottom is the equivalent command line, which you can copy into a script.

**Language:** use the **Language** menu at the top right of either window to switch between English and 简体中文. The window updates right away, even while it is running, and both windows remember the choice. The text comes from JSON files in [locales/](locales/). See [locales/README.md](locales/README.md) to edit a translation or add a language.

To try the GUI without cameras, set the bridge's server and local interface to `127.0.0.1` and press **Start mock Motive**, then **Start bridge**. In the test client, tick **Verify against mock**. Each window remembers its last settings in your home folder (`.natnet_dds_bridge_gui.json` and `.natnet_dds_client_gui.json`).

## Testing without Motive

```bash
python run_loopback_test.py
```

To test the unicast path at a higher frame rate:

```bash
python run_loopback_test.py --unicast --fps 240
```

To test the separate position and orientation topics (see [DDS topics](#dds-topics)):

```bash
python run_loopback_test.py --split-rigid-bodies
```

The mock server streams 3 rigid bodies, a 3-bone skeleton, labeled markers and a marker set. It also answers the NatNet handshake, model-definition requests and commands. Every value is a pure function of the frame number. With `--verify-mock`, the test client checks every received field (poses, ids, names, tracking flags, markers, timestamps) against those functions, so a PASS means the data went NatNet → bridge → DDS unchanged. You can also run the three programs in separate terminals:

```bash
python MockNatNetServer.py
```

```bash
python NatNetToDDS.py
```

```bash
python DDSTestClient.py --verify-mock
```

## DDS topics

| Topic | Type | Contents |
|---|---|---|
| `NatNet_FrameOfMocapData` | `NatNet::FrameOfMocapData` | One sample per Motive frame: frame number, timestamps, timecode, recording flag, rigid bodies, skeletons (with bones), labeled markers, marker sets |
| `NatNet_RigidBody` | `NatNet::RigidBody` (`@key id`) | One sample per rigid body per frame, with each body as its own DDS instance. Use this topic when you only need rigid body poses. |
| `<name>_pos` | `NatNet::RigidBodyPosition` | Split mode only, one topic per rigid body: its position, mean error and tracking flag, one sample per frame |
| `<name>_orientation` | `NatNet::RigidBodyOrientation` | Split mode only, one topic per rigid body: its orientation quaternion and tracking flag, one sample per frame |

**Topic prefix:** by default every topic name starts with `rt/basketball/`. The topics are actually named `rt/basketball/NatNet_FrameOfMocapData`, `rt/basketball/NatNet_RigidBody` and, in split mode, `rt/basketball/basketball_pos` and so on. The tables here show the names without the prefix.

- To change the prefix, use `--topic-prefix TEXT`. To use the plain names, use `--no-topic-prefix`. In either window, use **Prefix topic names with**.
- The prefix can contain letters, digits, `_` and `/`.
- The test client has the same setting, with the same default. It must match the bridge, otherwise the client finds no publishers.
- `rt/` is the prefix ROS 2 gives its topics on DDS. The prefix alone doesn't make these ROS 2 topics, though. A ROS 2 node also needs a message type with the same name and layout as the DDS type. These types are named `NatNet::…`, not ROS 2's `<package>::msg::dds_::<Type>_`.

**Split mode:** start the bridge with `--split-rigid-bodies`, or choose **Publish rigid bodies → position and orientation separately** in the bridge window. Each rigid body's position and orientation are then published as separate objects, on two topics named after the rigid body, instead of on `NatNet_RigidBody`. For example, a rigid body named `basketball` is published on `basketball_pos` and `basketball_orientation`.

- Every sample carries the rigid body's id, name, frame number and Motive timestamp. The position and orientation samples from one frame share the same frame number and DDS source timestamp, so a consumer can pair them up.
- DDS topic names can only contain letters, digits and `_`, so other characters in the name become `_`. For example, `my ball` becomes `my_ball_pos`.
- A rigid body whose name has no Latin letters or digits at all is published as `RigidBody_<id>_pos` and `RigidBody_<id>_orientation`. The bridge prints the topics it creates for each rigid body.
- The bridge creates a rigid body's topics when that body first appears. If you rename a rigid body in Motive, its data moves to topics with the new name.
- Only the bridge has this setting. The test client, in the window or on the command line, follows on its own: for every rigid body it sees on `NatNet_FrameOfMocapData`, it subscribes to `<name>_pos` and `<name>_orientation` as well as `NatNet_RigidBody`. Its rigid body table and metrics then show whichever form arrives. If the bridge doesn't publish `NatNet_FrameOfMocapData`, the client can't learn the names, so list them with `DDSTestClient.py --rigid-body-names basketball,Rocket`.

The full definitions are in [idl/NatNetDDS.idl](idl/NatNetDDS.idl). Positions are in meters (Motive's default) and orientations are quaternions (x, y, z, w). Rigid body, skeleton and bone names come from Motive's data descriptions. The bridge requests them on connect and again whenever Motive reports that the tracked models changed.

**QoS:** writers are BEST_EFFORT with KEEP_LAST 1, the usual choice for high-rate sensor streams. With `--reliable` the bridge uses RELIABLE writers. Best-effort readers match either kind of writer.

**Other languages:** generate code from the IDL, for example:

```bash
rtiddsgen -language C++11 -example <arch> idl/NatNetDDS.idl
```

Subscribe to the topic names above and the generated code works with this bridge.

## How the bridge uses the SDK

`NatNetToDDS.py` uses the SDK's `NatNetClient` as is for sockets, the connect handshake, NatNet version negotiation and packet decoding. The SDK files are unmodified. The bridge subclasses the client and changes these things:

- **Data descriptions:** the stock client only prints them. The subclass passes them to the bridge, which uses them for names.
- **Per-frame printing:** the stock client prints a console line for every frame, which slows high frame rates. The subclass decodes frames without that print.
- **No deep copies:** the SDK's `MoCapData` classes deep-copy every marker, rigid body and bone as it is stored, and copy whole marker sets a second time. The decoder never reuses those objects, so the bridge turns the copies off for `MoCapData`. Decoding is 3–4× faster as a result.
- **Frames before the handshake:** a server that is already streaming sends frames before it has told the bridge which NatNet version it uses. The SDK would decode those frames with the wrong layout and produce garbage, such as a timestamp of -1 and no rigid bodies, so the bridge skips them.
- **Receive buffer:** the bridge asks the OS for a 4 MB receive buffer on the NatNet data socket instead of the OS default. A short pause in the bridge then delays frames instead of dropping them. It logs the size it got, for example `[natnet] receive buffer 4096 KB`.
- **Timing:** it records when each packet arrived and reads Motive's clock frequency (see [Metrics](#metrics)).

Each decoded `MoCapData` frame is converted to the DDS types and written.

## Performance

The bridge handles each frame on one thread: decoding the NatNet packet, converting it, and writing it to DDS. The highest rate it can sustain therefore depends on how much is in each frame and on the speed of one CPU core. When frames come in faster than it can handle them, the receive buffer fills up and the bridge reports lost frames under **Packet loss**.

Measured end to end on an Apple M1 Pro with Cyclone DDS: the bridge on the command line, with the test client subscribed. "Highest rate" is the highest rate tested with no lost frames. Expect lower numbers on a slower CPU. The bridge window manages about 10–15% less, because the window shares the bridge's Python process.

| Scene | What the bridge publishes | Time per frame | Highest rate |
|---|---|---|---|
| Mock server (3 rigid bodies, 3 markers) | Both topics | 0.3 ms | ~3,000 Hz |
| 10 rigid bodies, 50 markers | Both topics | 1.3 ms | ~700 Hz |
| 10 rigid bodies, 50 markers | Split rigid bodies + frame topic | 1.45 ms | ~600 Hz |
| 10 rigid bodies, 50 markers | Split rigid bodies only (`--no-frames`) | 0.65 ms | ~1,000 Hz |
| 20 rigid bodies, 2 skeletons, 160 markers | Both topics | 3.5 ms | ~290 Hz (estimate: these frames are too large to send on a Mac, see below) |

To go faster:

- **Publish only what you use.** `NatNet_FrameOfMocapData` carries every marker, twice (in the marker sets and as labeled markers), and costs about three times as much to write as `NatNet_RigidBody`. If you only need rigid bodies, use `--no-frames` or untick it in the window. Split rigid bodies cost about 10% more than `NatNet_RigidBody`, because each rigid body becomes two DDS writes.
- **Stream less from Motive.** Turn off marker and skeleton data in Motive's streaming settings if you don't need them. The bridge then has less to decode.
- **Use RTI Connext if you can.** Cyclone's Python package serializes samples in Python. RTI's does it in compiled code, but its speed hasn't been measured here.

**Testing on a Mac:** macOS delivers multicast sent to its own address (`127.0.0.1`) at only about 180 packets per second, whatever the rate. To test rates above that on one Mac, use unicast: `--unicast` on the mock server and the bridge, or **Unicast** in the bridge window. macOS also won't send UDP packets larger than about 9 KB, so the mock can't stream large scenes there.

## Notes

- **RTI on macOS:** Connext's shared-memory transport may log `failed to initialize shared memory resource segment` errors. They are harmless, because RTI falls back to UDP. To fix them, raise the shm limits (see https://community.rti.com/kb/osx510).
- **Multicast on the same machine:** the mock server sends multicast on `127.0.0.1` by default. On a real network, pass `--client` with the IP of the interface facing Motive so the bridge joins the multicast group on that interface.
