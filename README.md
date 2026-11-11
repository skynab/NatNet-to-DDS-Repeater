# NatNet to DDS

A Python sample that receives OptiTrack Motive data with the NatNet SDK 4.5 Python client and republishes it on DDS ([RTI Connext DDS](https://www.rti.com/products/dds-standard) or any other DDS-RTPS implementation). It comes with a DDS test client that checks the data arrives intact. Everything is plain Python, so it runs on Windows, macOS and Linux.

```
Motive ──NatNet (UDP)──> NatNetToDDS.py ──DDS (RTPS)──> DDSTestClient.py
                                                  └──> any DDS app (C++, Java, ROS 2, …)
```

## Files

| File | What it is |
|---|---|
| `NatNetToDDS.py` | The bridge. It is based on the SDK's `PythonSample.py` and uses the SDK `NatNetClient`. |
| `DDSTestClient.py` | A DDS subscriber. It prints the data and reports fps, dropped frames and optional value checks. |
| `MockNatNetServer.py` | A simulated Motive server (NatNet 4.5) that streams a fixed synthetic scene, so you can test without cameras. |
| `run_loopback_test.py` | One-command end-to-end test: mock → bridge → DDS → test client. |
| `idl/NatNetDDS.idl` | The DDS data model. Use it with `rtiddsgen` to build consumers in other languages. |
| `natnet_dds/` | DDS type definitions (RTI and Cyclone) and a small backend wrapper. |
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

   `missed` counts gaps in Motive frame numbers. Run `python DDSTestClient.py --help` for options (`--duration`, `--quiet`, …).

## Testing without Motive

```bash
python run_loopback_test.py
```

To test the unicast path at a higher frame rate:

```bash
python run_loopback_test.py --unicast --fps 240
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

The full definitions are in [idl/NatNetDDS.idl](idl/NatNetDDS.idl). Positions are in meters (Motive's default) and orientations are quaternions (x, y, z, w). Rigid body, skeleton and bone names come from Motive's data descriptions. The bridge requests them on connect and again whenever Motive reports that the tracked models changed.

**QoS:** writers are BEST_EFFORT with KEEP_LAST 1, the usual choice for high-rate sensor streams. With `--reliable` the bridge uses RELIABLE writers. Best-effort readers match either kind of writer.

**Other languages:** generate code from the IDL, for example:

```bash
rtiddsgen -language C++11 -example <arch> idl/NatNetDDS.idl
```

Subscribe to the topic names above and the generated code works with this bridge.

## How the bridge uses the SDK

`NatNetToDDS.py` uses the SDK's `NatNetClient` as is for sockets, the connect handshake, NatNet version negotiation and packet decoding. It subclasses the client to add two hooks:

- **Data descriptions:** the stock client only prints them. The subclass passes them to the bridge, which uses them for names.
- **Per-frame printing:** the stock client prints a console line for every frame, which slows high frame rates. The subclass decodes frames without that print.

Each decoded `MoCapData` frame is converted to the DDS types and written.

## Notes

- **RTI on macOS:** Connext's shared-memory transport may log `failed to initialize shared memory resource segment` errors. They are harmless, because RTI falls back to UDP. To fix them, raise the shm limits (see https://community.rti.com/kb/osx510).
- **Multicast on the same machine:** the mock server sends multicast on `127.0.0.1` by default. On a real network, pass `--client` with the IP of the interface facing Motive so the bridge joins the multicast group on that interface.
