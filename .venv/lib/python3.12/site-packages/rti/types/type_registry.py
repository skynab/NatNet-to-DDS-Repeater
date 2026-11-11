# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

from typing import Optional

# A simple dictionary used by dds.DomainParticipant.register_idl_type to keep
# track of registered IDL-based Python types (and their TypeSupport)

_registered_types = {}


def register_type(type_name: str, type_class: type):
    _registered_types[type_name] = type_class


def get_type(type_name: str) -> Optional[type]:
    return _registered_types.get(type_name)
