# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

import dataclasses
import rti.idl_impl.unions as unions
import rti.idl_impl.type_plugin as idl_impl
import rti.idl_impl.reflection_utils as reflection_utils
import rti.idl_impl.sample_interpreter as sample_interpreter

# --- Serialization options ---------------------------------------------------


@dataclasses.dataclass
class SerializationOptions:
    """Configures certain global options that control how types are
    serialized.

    The singleton variable that can be modified is called serialization_options.
    It must be modified before the definition of the @struct- or
    @union-decorated types for which the options are to be applied.
    """

    allow_primitive_lists: bool = True


serialization_options = SerializationOptions()


def _get_sample_program_options(
    serialization_options: SerializationOptions,
) -> sample_interpreter.SampleProgramOptions:
    return sample_interpreter.SampleProgramOptions(
        allow_primitive_lists=serialization_options.allow_primitive_lists
    )


def _get_current_sample_program_options():
    return _get_sample_program_options(serialization_options)


# --- Decorators --------------------------------------------------------------


