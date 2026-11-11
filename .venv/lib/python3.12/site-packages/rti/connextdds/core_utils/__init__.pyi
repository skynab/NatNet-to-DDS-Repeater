"""Utilities from the RTI Connext DDS C implementation"""
import rti.connextdds.core_utils
import typing
import builtins

def enable_backtrace_on_segfault() -> None:
    pass
def free(ptr: int) -> None:
    pass
def get_buffer_address(arg0: Buffer) -> int:
    pass
def get_memoryview_from_string(arg0: int) -> memoryview:
    pass
def get_memoryview_from_wstring(arg0: int) -> memoryview:
    pass
def malloc(size: int) -> int:
    pass
def memcpy_buffer_objects(arg0: Buffer, arg1: Buffer) -> None:
    pass
def memcpy_from_buffer_object(arg0: int, arg1: Buffer, arg2: int) -> None:
    pass
def memcpy_to_buffer_object(arg0: Buffer, arg1: int, arg2: int) -> None:
    pass
def memcpy_to_buffer_object_slow(arg0: Buffer, arg1: int, arg2: int) -> None:
    pass
def strcpy_from_buffer_object(arg0: int, arg1: Buffer) -> None:
    pass
def string_realloc(arg0: int, arg1: int) -> int:
    pass
def wstrcpy_from_buffer_object(arg0: int, arg1: Buffer) -> None:
    pass
def wstring_realloc(arg0: int, arg1: int) -> int:
    pass
