"""NatNet DDS types for Eclipse Cyclone DDS (cyclonedds Python API).

Mirrors idl/NatNetDDS.idl exactly (same type names, member order and
extensibility) so samples interoperate with RTI Connext and any other
DDS-RTPS implementation.
"""
from dataclasses import dataclass, field

from cyclonedds.idl import IdlStruct
from cyclonedds.idl.annotations import final, key
from cyclonedds.idl.types import float32, float64, int32, int64, sequence, uint32


@final
@dataclass
class Vector3(IdlStruct, typename="NatNet::Vector3"):
    x: float32 = 0.0
    y: float32 = 0.0
    z: float32 = 0.0


@final
@dataclass
class Quaternion(IdlStruct, typename="NatNet::Quaternion"):
    x: float32 = 0.0
    y: float32 = 0.0
    z: float32 = 0.0
    w: float32 = 1.0


@final
@dataclass
class RigidBodyPose(IdlStruct, typename="NatNet::RigidBodyPose"):
    id: int32 = 0
    name: str = ""
    position: Vector3 = field(default_factory=Vector3)
    orientation: Quaternion = field(default_factory=Quaternion)
    mean_error: float32 = 0.0
    tracking_valid: bool = False


@final
@dataclass
class Skeleton(IdlStruct, typename="NatNet::Skeleton"):
    id: int32 = 0
    name: str = ""
    bones: sequence[RigidBodyPose] = field(default_factory=list)


@final
@dataclass
class MarkerSet(IdlStruct, typename="NatNet::MarkerSet"):
    name: str = ""
    markers: sequence[Vector3] = field(default_factory=list)


@final
@dataclass
class LabeledMarker(IdlStruct, typename="NatNet::LabeledMarker"):
    id: int32 = 0
    model_id: int32 = 0
    marker_id: int32 = 0
    position: Vector3 = field(default_factory=Vector3)
    size: float32 = 0.0
    occluded: bool = False
    residual: float32 = 0.0


@final
@dataclass
class FrameOfMocapData(IdlStruct, typename="NatNet::FrameOfMocapData"):
    frame_number: int32 = 0
    timestamp: float64 = 0.0
    timecode: uint32 = 0
    timecode_sub: uint32 = 0
    stamp_camera_mid_exposure: int64 = 0
    stamp_data_received: int64 = 0
    stamp_transmit: int64 = 0
    is_recording: bool = False
    tracked_models_changed: bool = False
    rigid_bodies: sequence[RigidBodyPose] = field(default_factory=list)
    skeletons: sequence[Skeleton] = field(default_factory=list)
    labeled_markers: sequence[LabeledMarker] = field(default_factory=list)
    marker_sets: sequence[MarkerSet] = field(default_factory=list)


@final
@dataclass
class RigidBody(IdlStruct, typename="NatNet::RigidBody"):
    id: int32 = 0
    key("id")
    name: str = ""
    frame_number: int32 = 0
    timestamp: float64 = 0.0
    position: Vector3 = field(default_factory=Vector3)
    orientation: Quaternion = field(default_factory=Quaternion)
    mean_error: float32 = 0.0
    tracking_valid: bool = False
