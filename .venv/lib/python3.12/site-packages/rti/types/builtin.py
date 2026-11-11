# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

from dataclasses import field
from typing import Sequence
from rti.types import struct as _struct
from rti.idl_impl.annotations import KeyAnnotation as _KeyAnnotation
from rti.idl_impl.type_hints import uint8 as _octet, int32 as _int32
from rti.idl_impl.type_utils import array_factory as _array_factory


@_struct
class String:
    """Built-in type consisting of a string

    This type can be used to create a dds.Topic, e.g.
    ```
    topic = dds.Topic(participant, "My Topic", String)
    ```
    """

    value: str = ""
    """The string payload"""


@_struct(member_annotations={"key": [_KeyAnnotation(True)]})
class KeyedString:
    """Built-in type consisting of a string payload and a second string that is
    the key.

    This type can be used to create a dds.Topic, e.g.
    ``topic = dds.Topic(participant, "My Topic", KeyedString)``.
    """

    key: str = ""
    """The key"""
    value: str = ""
    """The string payload"""


@_struct
class Bytes:
    """Built-in type consisting of a sequence of bytes

    This type can be used to create a dds.Topic, e.g.
    ``topic = dds.Topic(participant, "My Topic", Bytes)``.
    """

    value: Sequence[_octet] = field(default_factory=_array_factory(_octet))
    """The byte payload"""


@_struct(member_annotations={"key": [_KeyAnnotation(True)]})
class KeyedBytes:
    """Built-in type consisting of a sequence of bytes and a string that is the
    key.

    This type can be used to create a dds.Topic, e.g.
    ``topic = dds.Topic(participant, "My Topic", KeyedBytes)``.
    """

    key: str = ""
    """The key"""
    value: Sequence[_octet] = field(default_factory=_array_factory(_octet))
    """The byte payload"""


@_struct
class PingType:
    """The type used by the rtiddsping CLI utility, consisting of a single 32-bit integer.

    This type can be used to create a dds.Topic to interact with rtiddsping, e.g.
    ``topic = dds.Topic(participant, "PingTopic", PingType)``
    """

    number: _int32 = 0
