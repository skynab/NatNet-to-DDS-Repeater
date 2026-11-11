"""rti.connextdds.heap_monitoring monitor memory allocations done by the middleware on the native heap."""
import rti.connextdds.heap_monitoring
import typing
import builtins

class HeapMonitoringParams():
    def __eq__(self, arg0: rti.connextdds.heap_monitoring.HeapMonitoringParams) -> bool: 
        """
        Test for equality.
        """
    def __init__(self, snapshot_output_format: rti.connextdds.heap_monitoring.SnapshotOutputFormat = SnapshotOutputFormat.STANDARD, snapshot_content_format: rti.connextdds.heap_monitoring.SnapshotContentFormat = SnapshotOutputFormat.DEFAULT) -> None: 
        """
        Create parameters for heap monitoring.
        """
    def __ne__(self, arg0: rti.connextdds.heap_monitoring.HeapMonitoringParams) -> bool: 
        """
        Test for inequality.
        """
    @builtins.property
    def snapshot_content_format(self) -> SnapshotContentFormat:
        """
        Information included in snapshot output.

        :type: SnapshotContentFormat
        """
    @snapshot_content_format.setter
    def snapshot_content_format(self, arg1: SnapshotContentFormat) -> None:
        """
        Information included in snapshot output.
        """
    @builtins.property
    def snapshot_output_format(self) -> SnapshotOutputFormat:
        """
        Format of the snapshot output.

        :type: SnapshotOutputFormat
        """
    @snapshot_output_format.setter
    def snapshot_output_format(self, arg1: SnapshotOutputFormat) -> None:
        """
        Format of the snapshot output.
        """
    __hash__: NoneType
    pass
class SnapshotContentFormat():
    class SnapshotContentFormat():
        """
        Members:

          TOPIC : Add the topic to the snapshot of heap monitoring.

          FUNCTION : Add the function name to the snapshot of heap monitoring.

          ACTIVITY : Add the activity context to the snapshot of heap monitoring. The user can select the information that will be part of the activity context by using the API activity_context.set_attribute_mask.

          DEFAULT : Add all the optional attributes to the snapshot of heap monitoring.

          MINIMAL : Not add any optional attribute to the snapshot of heap monitoring.
        """
        def __eq__(self, other: object) -> bool: ...
        def __getstate__(self) -> int: ...
        def __hash__(self) -> int: ...
        def __index__(self) -> int: ...
        def __init__(self, value: int) -> None: ...
        def __int__(self) -> int: ...
        def __ne__(self, other: object) -> bool: ...
        def __repr__(self) -> str: ...
        def __setstate__(self, state: int) -> None: ...
        def __str__(self) -> str: ...
        @builtins.property
        def name(self) -> str:
            """
            :type: str
            """
        @builtins.property
        def value(self) -> int:
            """
            :type: int
            """
        ACTIVITY: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
        DEFAULT: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
        FUNCTION: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
        MINIMAL: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
        TOPIC: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
        __members__: dict
        pass
    def __eq__(self, arg0: rti.connextdds.heap_monitoring.SnapshotContentFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __ge__(self, arg0: rti.connextdds.heap_monitoring.SnapshotContentFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __gt__(self, arg0: rti.connextdds.heap_monitoring.SnapshotContentFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    @typing.overload
    def __init__(self) -> None: 
        """
        Initializes enum to 0.
        """
    @typing.overload
    def __init__(self, arg0: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat) -> None: 
        """
        Copy constructor.
        """
    def __int__(self) -> rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat: 
        """
        Int conversion.
        """
    def __le__(self, arg0: rti.connextdds.heap_monitoring.SnapshotContentFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __lt__(self, arg0: rti.connextdds.heap_monitoring.SnapshotContentFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __ne__(self, arg0: rti.connextdds.heap_monitoring.SnapshotContentFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __str__(self) -> str: 
        """
        String conversion.
        """
    @builtins.property
    def underlying(self) -> SnapshotContentFormat.SnapshotContentFormat:
        """
        Retrieves the actual enumerated value.

        :type: SnapshotContentFormat.SnapshotContentFormat
        """
    ACTIVITY: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
    DEFAULT: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
    FUNCTION: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
    MINIMAL: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
    TOPIC: rti.connextdds.heap_monitoring.SnapshotContentFormat.SnapshotContentFormat
    __hash__: NoneType
    pass
class SnapshotOutputFormat():
    class SnapshotOutputFormat():
        """
        Members:

          STANDARD : The output of the snapshot will be in plain text.

          COMPRESSED : The output of the snapshot will be compressed using Zlib techonology.

        The file can be uncompressed using zlib-flate.
        """
        def __eq__(self, other: object) -> bool: ...
        def __getstate__(self) -> int: ...
        def __hash__(self) -> int: ...
        def __index__(self) -> int: ...
        def __init__(self, value: int) -> None: ...
        def __int__(self) -> int: ...
        def __ne__(self, other: object) -> bool: ...
        def __repr__(self) -> str: ...
        def __setstate__(self, state: int) -> None: ...
        def __str__(self) -> str: ...
        @builtins.property
        def name(self) -> str:
            """
            :type: str
            """
        @builtins.property
        def value(self) -> int:
            """
            :type: int
            """
        COMPRESSED: rti.connextdds.heap_monitoring.SnapshotOutputFormat.SnapshotOutputFormat
        STANDARD: rti.connextdds.heap_monitoring.SnapshotOutputFormat.SnapshotOutputFormat
        __members__: dict
        pass
    def __eq__(self, arg0: rti.connextdds.heap_monitoring.SnapshotOutputFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __ge__(self, arg0: rti.connextdds.heap_monitoring.SnapshotOutputFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __gt__(self, arg0: rti.connextdds.heap_monitoring.SnapshotOutputFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    @typing.overload
    def __init__(self) -> None: 
        """
        Initializes enum to 0.
        """
    @typing.overload
    def __init__(self, arg0: rti.connextdds.heap_monitoring.SnapshotOutputFormat.SnapshotOutputFormat) -> None: 
        """
        Copy constructor.
        """
    def __int__(self) -> rti.connextdds.heap_monitoring.SnapshotOutputFormat.SnapshotOutputFormat: 
        """
        Int conversion.
        """
    def __le__(self, arg0: rti.connextdds.heap_monitoring.SnapshotOutputFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __lt__(self, arg0: rti.connextdds.heap_monitoring.SnapshotOutputFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __ne__(self, arg0: rti.connextdds.heap_monitoring.SnapshotOutputFormat) -> bool: 
        """
        Apply operator to underlying enumerated values.
        """
    def __str__(self) -> str: 
        """
        String conversion.
        """
    @builtins.property
    def underlying(self) -> SnapshotOutputFormat.SnapshotOutputFormat:
        """
        Retrieves the actual enumerated value.

        :type: SnapshotOutputFormat.SnapshotOutputFormat
        """
    COMPRESSED: rti.connextdds.heap_monitoring.SnapshotOutputFormat.SnapshotOutputFormat
    STANDARD: rti.connextdds.heap_monitoring.SnapshotOutputFormat.SnapshotOutputFormat
    __hash__: NoneType
    pass
def disable() -> None:
    """
    Stop monitoring the heap memory used by RTI Connext.
    """
@typing.overload
def enable() -> bool:
    """
    Start monitoring the heap memory used by RTI Connext. Must be called before any using any other int the RTI Connext library.
    """
@typing.overload
def enable(params: rti.connextdds.heap_monitoring.HeapMonitoringParams) -> bool:
    """
    Start monitoring the heap memory used by RTI Connext with params. Must be called before any using any other in the RTI Connext library.
    """
def pause() -> bool:
    """
    Pauses heap monitoring.
    """
def resume() -> bool:
    """
    Resumes heap monitoring.
    """
def take_snapshot(filename: str, print_details: bool = False) -> bool:
    """
    Saves the current heap memory usage in a file.
    """
