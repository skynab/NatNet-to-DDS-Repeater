# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

from dataclasses import dataclass
from enum import IntEnum

# --- Annotation classes ------------------------------------------------------


class ParameterKind(IntEnum):
    IN = 0
    OUT = 1
    INOUT = 2


@dataclass
class ParameterKindAnnotation:
    value: ParameterKind = ParameterKind.IN
