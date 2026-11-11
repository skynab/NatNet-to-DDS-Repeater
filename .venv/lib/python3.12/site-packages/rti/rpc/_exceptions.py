# Copyright (c) 2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.


from enum import IntEnum
from typing import Any


class RemoteExceptionCode(IntEnum):
    """Enumeration of the standard error codes that can be reported by a
    service in the remoteEx field of the Result type of an RPC call."""

    # Note that OK will never be used. If an operation is succesfull the
    # remoteEx field will never be set.
    OK = 0
    UNSUPPORTED = 1
    INVALID_ARGUMENT = 2
    OUT_OF_RESOURCES = 3
    UNKNOWN_OPERATION = 4
    UNKNOWN_EXCEPTION = 5


class RemoteError(Exception):
    """Base class for all built-in exceptions that can be reported by a service
    and thrown by a client. This doesn't include user-defined exceptions.
    """


class RemoteUnsupportedOperationError(RemoteError):
    """Exception thrown by a client operation when the server indicates that
    the operation is not supported.
    """

    def __init__(self) -> None:
        super().__init__("The requested operation is not supported by the service")


class RemoteInvalidArgumentError(RemoteError):
    """Exception thrown by a client operation when the server indicates that
    the operation failed because of an invalid argument.
    """

    def __init__(self) -> None:
        super().__init__("An invalid argument was provided to the service operation")


class RemoteOutOfResourcesError(RemoteError):
    """Exception thrown by a client operation when the server indicates that
    the operation failed because the server ran out of resources.
    """

    def __init__(self) -> None:
        super().__init__(
            "The service has run out of resources to fulfill the operation"
        )


class RemoteUnknownOperationError(RemoteError):
    """Exception thrown by a client operation when the server indicates that
    the operation is unknown to the server.
    """

    def __init__(self) -> None:
        super().__init__("The requested operation doesn't exist in the service")


class RemoteUnknownExceptionError(RemoteError):
    """Exception thrown by a client operation when the server operation fails
    with an exception that is not declared in the interface.
    """

    def __init__(self) -> None:
        super().__init__("An unknown exception has occurred in the service")


def throw_from_remote_ex_code(remote_ex_code: int) -> None:
    """Throw the appropriate exception based on the given remote exception code."""

    if remote_ex_code == RemoteExceptionCode.OK.value:
        return

    if remote_ex_code == RemoteExceptionCode.UNSUPPORTED.value:
        raise RemoteUnsupportedOperationError()
    elif remote_ex_code == RemoteExceptionCode.INVALID_ARGUMENT.value:
        raise RemoteInvalidArgumentError()
    elif remote_ex_code == RemoteExceptionCode.OUT_OF_RESOURCES.value:
        raise RemoteOutOfResourcesError()
    elif remote_ex_code == RemoteExceptionCode.UNKNOWN_OPERATION.value:
        raise RemoteUnknownOperationError()
    else:
        raise RemoteUnknownExceptionError()


def get_remote_ex_code_from_ex(ex: Any) -> int:
    """Get the remote exception code that corresponds to the given exception type."""

    if isinstance(ex, RemoteUnsupportedOperationError):
        return RemoteExceptionCode.UNSUPPORTED.value
    elif isinstance(ex, RemoteInvalidArgumentError):
        return RemoteExceptionCode.INVALID_ARGUMENT.value
    elif isinstance(ex, RemoteOutOfResourcesError):
        return RemoteExceptionCode.OUT_OF_RESOURCES.value
    elif isinstance(ex, RemoteUnknownOperationError):
        return RemoteExceptionCode.UNKNOWN_OPERATION.value
    else:
        return RemoteExceptionCode.UNKNOWN_EXCEPTION.value
