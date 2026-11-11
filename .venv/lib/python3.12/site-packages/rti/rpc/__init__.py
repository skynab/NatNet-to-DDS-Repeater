# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

from ._basic import SimpleReplier
from ._async import Requester, Replier

from ._rpc import (
    service,
    operation,
    Service,
    ClientBase,
    get_interface_types,
    ByRef,
)

from ._exceptions import (
    RemoteError,
    RemoteUnsupportedOperationError,
    RemoteInvalidArgumentError,
    RemoteOutOfResourcesError,
    RemoteUnknownExceptionError,
    RemoteUnknownOperationError,
)

from . import _annotations as annotations

__all__ = [
    "SimpleReplier",
    "Requester",
    "Replier",
    "service",
    "operation",
    "Service",
    "ClientBase",
    "RemoteError",
    "RemoteUnsupportedOperationError",
    "RemoteInvalidArgumentError",
    "RemoteOutOfResourcesError",
    "RemoteUnknownExceptionError",
    "RemoteUnknownOperationError",
    "get_interface_types",
    "ByRef",
]

# --- Member annotations ------------------------------------------------------

in_param = annotations.ParameterKindAnnotation(annotations.ParameterKind.IN)
out_param = annotations.ParameterKindAnnotation(annotations.ParameterKind.OUT)
inout_param = annotations.ParameterKindAnnotation(annotations.ParameterKind.INOUT)
