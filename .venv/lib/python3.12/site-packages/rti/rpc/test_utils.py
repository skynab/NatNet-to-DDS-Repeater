# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

import pytest

import asyncio
import copy
import inspect

import rti.connextdds as dds
import rti.rpc as rpc

from rti.idl_impl.test_utils import (
    get_test_domain,
    get_test_participant_qos,
    IdlValueGenerator,
)

from rti.idl_impl import reflection_utils

"""Test utilities for the RPC API.

Provides utilities to automatically create a service and client for a given
IDL service type.
"""

# --- RPC test utilities --------------------------------------------------


def get_rpc_test_participant_qos():
    qos = get_test_participant_qos()
    qos.resource_limits.contentfilter_property_max_length = 280
    return qos


def create_rpc_participant():
    return dds.DomainParticipant(get_test_domain(), get_rpc_test_participant_qos())


class RpcFixture:
    def __init__(
        self,
        participant,
        service_type,
        create_service=True,
        create_client=True,
        use_kwargs=True,
    ):
        self.service_type = service_type
        self.participant = participant or create_rpc_participant()
        self.service = None
        self.client = None
        self.service_task = None
        self.use_kwargs = use_kwargs

        service_name = f"{self.service_type.__name__}Service"

        if create_service:
            self.service = rpc.Service(
                self.service_type.service_impl(), self.participant, service_name
            )

        if create_client:
            client_impl = type(
                f"{self.service_type.__name__}Client",
                (
                    self.service_type,
                    rpc.ClientBase,
                ),
                {},
            )
            self.client = client_impl(
                self.participant, service_name, max_wait_per_call=dds.Duration(20)
            )

    async def _run_service(self):
        """Run the service until it is cancelled"""
        try:
            await self.service.run(close_on_cancel=True)
        except asyncio.CancelledError:
            pass

    def initialize(self):
        """Start the service"""
        if self.service is not None:
            self.service_task = asyncio.create_task(self._run_service())

    def _populate_expected_values(self, seed):
        """
        Populate in a map that lives in the self.service_type.service_impl
        the expected values for each argument of the service operations
        and the return value.
        This way we can call the operations with the expected values
        and the generated code will check that the received arguments
        are the expected ones. For the return value we do the same,
        the generated code will return the expected value so that
        we can check that the returned value is the expected one.
        To get the expected values we rely on the internal In_structs
        and Result_unions.
        """
        operations = inspect.getmembers(self.service_type, inspect.isfunction)
        in_structs = self.service_type.call_type.in_structs.values()
        out_unions = self.service_type.return_type.result_unions.values()

        for method_name, method in operations:

            in_struct = [v for k, v in in_structs if k == method_name][0]
            in_members = vars(IdlValueGenerator(in_struct).create_test_data(seed))

            out_struct = [v for k, v in out_unions if k == method_name][0].default_value
            out_members = vars(IdlValueGenerator(out_struct).create_test_data(seed + 1))

            parameters = inspect.signature(method).parameters
            default_out_struct = None
            for param_name in parameters.keys():
                if param_name == "self":
                    continue

                key = f"{method_name}_{param_name}"
                value = None

                if param_name in in_members:
                    value = in_members[param_name]
                else:
                    # If the parameter is out, the default value will be provided
                    # to the method. So we can check that the generation of the
                    # parameter in the service is correct.
                    if default_out_struct is None:
                        default_out_struct = out_struct()

                    assert hasattr(default_out_struct, param_name)
                    value = getattr(default_out_struct, param_name)

                if (
                    reflection_utils.get_origin(parameters[param_name].annotation)
                    is rpc.ByRef
                ):
                    value = rpc.ByRef(value)

                self.service_type.service_impl.rpc_test_values[key] = value

                # Modify the out members with the expected values
                if param_name in out_members:
                    self.service_type.service_impl.rpc_test_values[
                        f"{method_name}_{param_name}_out"
                    ] = (
                        out_members[param_name]
                        if reflection_utils.get_origin(
                            parameters[param_name].annotation
                        )
                        is not rpc.ByRef
                        else rpc.ByRef(out_members[param_name])
                    )

            if "return_" in out_members:
                self.service_type.service_impl.rpc_test_values[
                    f"{method_name}_return"
                ] = out_members["return_"]

    def _get_params(self, operation):
        """Get the parameters for the operation"""
        args = []
        kwargs = {}
        out_args = []
        out_kwargs = {}

        signarture = inspect.signature(operation)

        for param_name, param in signarture.parameters.items():
            if param_name == "self":
                continue

            # All the parameters must have an associated annotation
            assert param.annotation != inspect.Parameter.empty

            value = self.service_type.service_impl.rpc_test_values[
                f"{operation.__name__}_{param_name}"
            ]
            out_value = self.service_type.service_impl.rpc_test_values.get(
                f"{operation.__name__}_{param_name}_out", value
            )

            if self.use_kwargs:
                kwargs[param_name] = value
                out_kwargs[param_name] = out_value
            else:
                args.append(value)
                out_args.append(out_value)

        return args, kwargs, out_args, out_kwargs

    def _get_return(self, operation):
        """Get the return value for the operation"""
        return self.service_type.service_impl.rpc_test_values.get(
            f"{operation.__name__}_return",
            None,
        )

    def _get_exceptions(self, operation):
        """Get the exceptions that the operation can raise"""
        exception_key = f"{operation.__name__}_exception"
        exceptions = getattr(operation, "_raises", [])
        for exception in exceptions:
            self.service_type.service_impl.rpc_test_values[exception_key] = exception()
            yield exception

        self.service_type.service_impl.rpc_test_values.pop(exception_key, None)

    async def _call_operation(self, name, operation):
        """
        Call an operation and check the return value.
        1. If the operation raises an exception, check that the exception is raised.
        2. If the operation returns a value, check that the return value is correct.
        3. If the operation does not return a value, check that the operation completes
           without error.
        """
        args, kwargs, out_args, out_kargs = self._get_params(operation)
        return_value = self._get_return(operation)
        method_ref = getattr(self.client, name)

        modified_args = copy.deepcopy(args)
        modified_kwargs = copy.deepcopy(kwargs)

        # We call the operation without raising any exception
        if return_value is None:
            await method_ref(*modified_args, **modified_kwargs)
        else:
            assert return_value == await method_ref(*modified_args, **modified_kwargs)

        assert out_args == modified_args
        assert out_kargs == modified_kwargs

        # Check that the operation raises the expected exceptions
        for exception in self._get_exceptions(operation):
            modified_args = copy.deepcopy(args)
            modified_kwargs = copy.deepcopy(kwargs)
            with pytest.raises(exception):
                await method_ref(*modified_args, **modified_kwargs)

    async def execute_operations(self, seed=0, close_on_completion=True):
        """Call all the operations defined by the service"""

        if self.client is None:
            raise ValueError("There is no client to execute the operations")

        # Check that a service is available
        assert (await self.client.wait_for_service_async(dds.Duration(20))) is True

        self._populate_expected_values(seed)

        operations = inspect.getmembers(self.service_type, inspect.isfunction)
        for name, operation in operations:
            assert hasattr(operation, "_is_rpc_operation")
            await self._call_operation(name, operation)

        self.service_type.service_impl.rpc_test_values.clear()

        # Close the client and cancel and close the service
        if close_on_completion:
            await self.close()

    async def close(self):
        """Close the service and client"""
        if self.service_task is not None:
            self.service_task.cancel()
            await self.service_task
        if self.client is not None:
            self.client.close()
