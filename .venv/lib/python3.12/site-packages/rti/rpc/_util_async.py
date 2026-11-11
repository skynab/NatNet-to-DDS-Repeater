# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.


from typing import Union

import rti.connextdds
from . import _util


async def wait_for_samples_async(
    reader,  # type: Union[rti.connextdds.DynamicData.DataReader, object]
    min_count,  # type: int
    max_wait,  # type: rti.connextdds.Duration
    waitset,  # type: rti.connextdds.WaitSet
    initial_condition,  # type: rti.connextdds.ICondition
    condition,  # type: rti.connextdds.ICondition
):
    # type: (...) -> bool
    if min_count == rti.connextdds.LENGTH_UNLIMITED:
        min_count = _util.INT_MAX

    sample_count = (
        reader.select()
        .max_samples(min_count)
        .condition(initial_condition)
        .read_loaned()
        .length
    )
    min_count -= sample_count

    participant = reader.subscriber.participant
    remaining_wait = max_wait if min_count == 1 else rti.connextdds.Duration(max_wait)

    while min_count > 0:
        if min_count == 1:
            if not await waitset.wait_one_async(remaining_wait):
                return False
        else:
            before_time = participant.current_time
            if not await waitset.wait_one_async(remaining_wait):
                return False
            wait_time = participant.current_time - before_time
            remaining_wait -= wait_time

        if min_count > 1:
            sample_count = (
                reader.select()
                .max_samples(min_count)
                .condition(condition)
                .read_loaned()
                .length
            )
            min_count -= sample_count
        else:
            min_count -= 1

    return True
