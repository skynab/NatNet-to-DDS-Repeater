"""Save network traffic into a capture file for further analysis."""
import rti.connextdds.network_capture
import typing
import builtins
import rti.connextdds

class ContentKindMask():
    def __and__(self, arg0: rti.connextdds.network_capture.ContentKindMask) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Bitwise logical AND of masks.
        """
    def __bool__(self) -> bool: 
        """
        Test if any bits are set.
        """
    def __contains__(self, arg0: rti.connextdds.network_capture.ContentKindMask) -> bool: ...
    def __eq__(self, arg0: rti.connextdds.network_capture.ContentKindMask) -> bool: 
        """
        Compare masks for equality.
        """
    def __getitem__(self, arg0: int) -> bool: 
        """
        Get individual mask bit.
        """
    def __iand__(self, arg0: rti.connextdds.network_capture.ContentKindMask) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Set mask to logical AND with another mask.
        """
    def __ilshift__(self, arg0: int) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Left shift bits in mask.
        """
    @typing.overload
    def __init__(self) -> None: 
        """
        Create a ContentKindMask with no bits set.
        """
    @typing.overload
    def __init__(self, value: int) -> None: 
        """
        Creates a mask from the bits in an integer.
        """
    def __int__(self) -> int: 
        """
        Convert mask to int.
        """
    def __ior__(self, arg0: rti.connextdds.network_capture.ContentKindMask) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Set mask to logical OR with another mask.
        """
    def __irshift__(self, arg0: int) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Right shift bits in mask.
        """
    def __ixor__(self, arg0: rti.connextdds.network_capture.ContentKindMask) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Set mask to logical XOR with another mask.
        """
    def __lshift__(self, arg0: int) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Left shift bits in mask.
        """
    def __ne__(self, arg0: rti.connextdds.network_capture.ContentKindMask) -> bool: 
        """
        Compare masks for inequality.
        """
    def __or__(self, arg0: rti.connextdds.network_capture.ContentKindMask) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Bitwise logical OR of masks.
        """
    def __repr__(self) -> str: 
        """
        Convert mask to string.
        """
    def __rshift__(self, arg0: int) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Right shift bits in mask.
        """
    def __setitem__(self, arg0: int, arg1: bool) -> None: 
        """
        Set individual mask bit
        """
    def __str__(self) -> str: 
        """
        Convert mask to string.
        """
    def __xor__(self, arg0: rti.connextdds.network_capture.ContentKindMask) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Bitwise logical XOR of masks.
        """
    @typing.overload
    def flip(self) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Flip all bits in the mask.
        """
    @typing.overload
    def flip(self, pos: int) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Flip the mask bit at the specified position.
        """
    @typing.overload
    def reset(self) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Clear all bits in the mask.
        """
    @typing.overload
    def reset(self, pos: int) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Clear the mask bit at the specified position.
        """
    @typing.overload
    def set(self) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Set all bits in the mask.
        """
    @typing.overload
    def set(self, pos: int, value: bool = True) -> rti.connextdds.network_capture.ContentKindMask: 
        """
        Set the mask bit at the specified position to the provided value (default: true).
        """
    def test(self, pos: int) -> bool: 
        """
        Test whether the mask bit at position "pos" is set.
        """
    def test_all(self) -> bool: 
        """
        Test if all bits are set.
        """
    def test_any(self) -> bool: 
        """
        Test if any bits are set.
        """
    def test_none(self) -> bool: 
        """
        Test if none of the bits are set.
        """
    @builtins.property
    def count(self) -> int:
        """
        Returns the number of bits set in the mask.

        :type: int
        """
    @builtins.property
    def size(self) -> int:
        """
        Returns the number of bits in the mask type.

        :type: int
        """
    ALL: rti.connextdds.network_capture.ContentKindMask
    DEFAULT: rti.connextdds.network_capture.ContentKindMask
    ENCRYPTED: rti.connextdds.network_capture.ContentKindMask
    NONE: rti.connextdds.network_capture.ContentKindMask
    USER: rti.connextdds.network_capture.ContentKindMask
    __hash__: NoneType
    pass
class NetworkCaptureParams():
    def __eq__(self, arg0: rti.connextdds.network_capture.NetworkCaptureParams) -> bool: 
        """
        Test for equality.
        """
    def __init__(self) -> None: 
        """
        Create a default NetworkCaptureParams.
        """
    def __ne__(self, arg0: rti.connextdds.network_capture.NetworkCaptureParams) -> bool: 
        """
        Test for inequality.
        """
    @builtins.property
    def checkpoint_thread_settings(self) -> rti.connextdds.ThreadSettings:
        """
        Checkpoint thread properties.

        :type: rti.connextdds.ThreadSettings
        """
    @checkpoint_thread_settings.setter
    def checkpoint_thread_settings(self, arg1: rti.connextdds.ThreadSettings) -> None:
        """
        Checkpoint thread properties.
        """
    @builtins.property
    def dropped_content(self) -> ContentKindMask:
        """
        The type of content excluded from capture files.

        :type: ContentKindMask
        """
    @dropped_content.setter
    def dropped_content(self, arg1: ContentKindMask) -> None:
        """
        The type of content excluded from capture files.
        """
    @builtins.property
    def frame_queue_size(self) -> int:
        """
        Set the size of the frame queue.

        :type: int
        """
    @frame_queue_size.setter
    def frame_queue_size(self, arg1: int) -> None:
        """
        Set the size of the frame queue.
        """
    @builtins.property
    def parse_encrypted_content(self) -> bool:
        """
        Toggle for parsing encrypted contents.

        :type: bool
        """
    @parse_encrypted_content.setter
    def parse_encrypted_content(self, arg1: bool) -> None:
        """
        Toggle for parsing encrypted contents.
        """
    @builtins.property
    def traffic(self) -> TrafficKindMask:
        """
        The traffic direction to capture.

        :type: TrafficKindMask
        """
    @traffic.setter
    def traffic(self, arg1: TrafficKindMask) -> None:
        """
        The traffic direction to capture.
        """
    @builtins.property
    def transports(self) -> rti.connextdds.StringSeq:
        """
        List of transports to capture.

        :type: rti.connextdds.StringSeq
        """
    @transports.setter
    def transports(self, arg1: rti.connextdds.StringSeq) -> None:
        """
        List of transports to capture.
        """
    __hash__: NoneType
    pass
class TrafficKindMask():
    def __and__(self, arg0: rti.connextdds.network_capture.TrafficKindMask) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Bitwise logical AND of masks.
        """
    def __bool__(self) -> bool: 
        """
        Test if any bits are set.
        """
    def __contains__(self, arg0: rti.connextdds.network_capture.TrafficKindMask) -> bool: ...
    def __eq__(self, arg0: rti.connextdds.network_capture.TrafficKindMask) -> bool: 
        """
        Compare masks for equality.
        """
    def __getitem__(self, arg0: int) -> bool: 
        """
        Get individual mask bit.
        """
    def __iand__(self, arg0: rti.connextdds.network_capture.TrafficKindMask) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Set mask to logical AND with another mask.
        """
    def __ilshift__(self, arg0: int) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Left shift bits in mask.
        """
    @typing.overload
    def __init__(self) -> None: 
        """
        Create a TrafficKindMask with no bits set.
        """
    @typing.overload
    def __init__(self, value: int) -> None: 
        """
        Creates a mask from the bits in an integer.
        """
    def __int__(self) -> int: 
        """
        Convert mask to int.
        """
    def __ior__(self, arg0: rti.connextdds.network_capture.TrafficKindMask) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Set mask to logical OR with another mask.
        """
    def __irshift__(self, arg0: int) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Right shift bits in mask.
        """
    def __ixor__(self, arg0: rti.connextdds.network_capture.TrafficKindMask) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Set mask to logical XOR with another mask.
        """
    def __lshift__(self, arg0: int) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Left shift bits in mask.
        """
    def __ne__(self, arg0: rti.connextdds.network_capture.TrafficKindMask) -> bool: 
        """
        Compare masks for inequality.
        """
    def __or__(self, arg0: rti.connextdds.network_capture.TrafficKindMask) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Bitwise logical OR of masks.
        """
    def __repr__(self) -> str: 
        """
        Convert mask to string.
        """
    def __rshift__(self, arg0: int) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Right shift bits in mask.
        """
    def __setitem__(self, arg0: int, arg1: bool) -> None: 
        """
        Set individual mask bit
        """
    def __str__(self) -> str: 
        """
        Convert mask to string.
        """
    def __xor__(self, arg0: rti.connextdds.network_capture.TrafficKindMask) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Bitwise logical XOR of masks.
        """
    @typing.overload
    def flip(self) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Flip all bits in the mask.
        """
    @typing.overload
    def flip(self, pos: int) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Flip the mask bit at the specified position.
        """
    @typing.overload
    def reset(self) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Clear all bits in the mask.
        """
    @typing.overload
    def reset(self, pos: int) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Clear the mask bit at the specified position.
        """
    @typing.overload
    def set(self) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Set all bits in the mask.
        """
    @typing.overload
    def set(self, pos: int, value: bool = True) -> rti.connextdds.network_capture.TrafficKindMask: 
        """
        Set the mask bit at the specified position to the provided value (default: true).
        """
    def test(self, pos: int) -> bool: 
        """
        Test whether the mask bit at position "pos" is set.
        """
    def test_all(self) -> bool: 
        """
        Test if all bits are set.
        """
    def test_any(self) -> bool: 
        """
        Test if any bits are set.
        """
    def test_none(self) -> bool: 
        """
        Test if none of the bits are set.
        """
    @builtins.property
    def count(self) -> int:
        """
        Returns the number of bits set in the mask.

        :type: int
        """
    @builtins.property
    def size(self) -> int:
        """
        Returns the number of bits in the mask type.

        :type: int
        """
    ALL: rti.connextdds.network_capture.TrafficKindMask
    DEFAULT: rti.connextdds.network_capture.TrafficKindMask
    IN: rti.connextdds.network_capture.TrafficKindMask
    NONE: rti.connextdds.network_capture.TrafficKindMask
    OUT: rti.connextdds.network_capture.TrafficKindMask
    __hash__: NoneType
    pass
def disable() -> bool:
    """
    Disable network capture. Must delete captured Domain Participants and stop capture before calling disable.
    """
def enable() -> bool:
    """
    Enable network capture.

    Must be called before any using any other int the RTI Connext library.
    """
@typing.overload
def pause() -> bool:
    """
    Pause network capture.
    """
@typing.overload
def pause(participant: rti.connextdds.DomainParticipant) -> bool:
    """
    Pause network capture.
    """
@typing.overload
def resume() -> bool:
    """
    Resume network capture.
    """
@typing.overload
def resume(participant: rti.connextdds.DomainParticipant) -> bool:
    """
    Resume network capture.
    """
def set_default_params(params: rti.connextdds.network_capture.NetworkCaptureParams) -> bool:
    """
    Set default network capture parameters.
    """
@typing.overload
def start(filename: str) -> bool:
    """
    Start network capture.
    """
@typing.overload
def start(participant: rti.connextdds.DomainParticipant, filename: str) -> bool:
    """
    Start network capture for a participant.
    """
@typing.overload
def start(filename: str, params: rti.connextdds.network_capture.NetworkCaptureParams) -> bool:
    """
    Start network capture with parameters.
    """
@typing.overload
def start(participant: rti.connextdds.DomainParticipant, filename: str, params: rti.connextdds.network_capture.NetworkCaptureParams) -> bool:
    """
    Start network capture with parameters for a participant.
    """
@typing.overload
def stop() -> bool:
    """
    Stop network capture.
    """
@typing.overload
def stop(participant: rti.connextdds.DomainParticipant) -> bool:
    """
    Stop network capture.
    """
