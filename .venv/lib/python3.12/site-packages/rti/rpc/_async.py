# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.


import rti.connextdds as dds
from . import _util
from . import _util_async
from . import _basic
from typing import Union, Optional, Callable


class Requester(_basic.Requester):
    """A Requester allows sending requests and receiving replies

    :param request_type: The type of the request data. It can be an ``@idl.struct``, an ``@idl.union``, or a dds.DynamicType. (See :ref:`types:Data Types`.)
    :param reply_type: The type of the reply data.
    :param participant: The DomainParticipant that will hold the request writer and reply reader.
    :param service_name: Name that will be used to derive the topic name, defaults to None (rely only on custom topics).
    :param request_topic: Topic object or name that will be used for the request data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).
    :param reply_topic: Topic object or name that will be used for the reply data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).
    :param datawriter_qos: QoS object to use for request writer, defaults to None (use the QoS defined by the built-in profile dds.BuiltinProfiles.pattern_rpc).
    :param datareader_qos: QoS object to use for reply reader, defaults to None (use the QoS defined by the built-in profile dds.BuiltinProfiles.pattern_rpc).
    :param publisher: Publisher used to create the request writer, defaults to None (use participant.builtin_publisher).
    :param subscriber: Subscriber used to create the reply reader, defaults to None (use participant.builtin_subscriber).
    :param on_reply_available: The callback that handles incoming replies.
    :param require_matching_service_on_send_request: Indicates whether send_request fails if no service has been discovered, default True.
    """

    def __init__(
        self,
        request_type: Union[type, dds.DynamicType],
        reply_type: Union[type, dds.DynamicType],
        participant: dds.DomainParticipant,
        service_name: Optional[str] = None,
        request_topic: Union[dds.Topic, dds.DynamicData.Topic, str, object] = None,
        reply_topic: Union[dds.Topic, dds.DynamicData.Topic, str, object] = None,
        datawriter_qos: Optional[dds.DataWriterQos] = None,
        datareader_qos: Optional[dds.DataReaderQos] = None,
        publisher: Optional[dds.Publisher] = None,
        subscriber: Optional[dds.Subscriber] = None,
        on_reply_available: Optional[Callable[[object], object]] = None,
        require_matching_service_on_send_request: bool = True,
    ) -> None:
        super(Requester, self).__init__(
            request_type,
            reply_type,
            participant,
            service_name,
            request_topic,
            reply_topic,
            datawriter_qos,
            datareader_qos,
            publisher,
            subscriber,
            on_reply_available,
            require_matching_service_on_send_request,
        )

    async def wait_for_service_async(self, max_wait: dds.Duration) -> bool:
        """Asynchronously waits for a Replier to be discovered.

        This method returns True if a Replier is discovered and
        ready to receive requests within the specified maximum wait. It
        returns False if it times out.
        """

        if self.closed:
            raise dds.AlreadyClosedError("Requester already closed")

        participant = self._writer.publisher.participant
        remaining_time = max_wait

        while (
            not self._can_send_request()
            or not self._reader._has_matched_publications_with_related_reader
        ):
            before_time = participant.current_time
            if not await self._service_waitset.wait_one_async(remaining_time):
                return False
            after_time = participant.current_time
            remaining_time -= after_time - before_time

            _ = self._reader.subscription_matched_status

        return True


    async def wait_for_replies_async(
        self,
        max_wait: dds.Duration,
        min_count: int = 1,
        related_request_id: Optional[dds.SampleIdentity] = None,
    ) -> bool:
        """Wait for received replies asynchronously.

        :param max_wait: Maximum time to wait for replies before timing out.
        :param min_count: Minimum number of replies to receive, default 1.
        :param related_request_id: The request id used to correlate replies, default None (receive any replies).
        :return: Boolean indicating whether min_count replies were received within max_wait time.
        """
        if related_request_id is None:
            return _util.wait_for_samples(
                self._reader,
                min_count,
                max_wait,
                self._waitset,
                self._any_sample_condition,
                self._notread_sample_condition,
            )
        else:
            initial_condition = dds.AnyDataReader._create_correlation_condition(
                self._reader, dds.SampleState.ANY, related_request_id.sequence_number
            )
            correlation_condition = dds.AnyDataReader._create_correlation_condition(
                self._reader,
                dds.SampleState.NOT_READ,
                related_request_id.sequence_number,
            )
            waitset = dds.WaitSet()
            waitset += correlation_condition
            try:
                return await _util_async.wait_for_samples_async(
                    self._reader,
                    min_count,
                    max_wait,
                    waitset,
                    initial_condition,
                    correlation_condition,
                )
            finally:
                waitset.detach_all()


class Replier(_basic.Replier):
    """A replier object for handling request-reply interactions with DDS.

    :param request_type: The type of the request data.
    :param reply_type: The type of the reply data.
    :param participant: The DomainParticipant that will hold the reply writer and request reader.
    :param service_name: Name that will be used to derive the topic name, defaults to None (rely only on custom topics).
    :param request_topic: Topic object or name that will be used for the request data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).
    :param reply_topic: Topic object or name that will be used for the reply data, must be set if service_name is None, otherwise overrides service_name, defaults to None (use service_name).
    :param datawriter_qos: QoS object to use for reply writer, defaults to None (use the QoS defined by the built-in profile dds.BuiltinProfiles.pattern_rpc).
    :param datareader_qos: QoS object to use for request reader, defaults to None (use the QoS defined by the built-in profile dds.BuiltinProfiles.pattern_rpc).
    :param publisher: Publisher used to create the request writer, defaults to None (use participant.builtin_publisher).
    :param subscriber: Subscriber used to create the reply reader, defaults to None (use participant.builtin_subscriber).
    :param on_reply_available: The callback that handles incoming requests (optional).
    """

    def __init__(
        self,
        request_type: Union[type, dds.DynamicType],
        reply_type: Union[type, dds.DynamicType],
        participant: dds.DomainParticipant,
        service_name: Optional[str] = None,
        request_topic: Optional[
            Union[
                dds.DynamicData.Topic, dds.DynamicData.ContentFilteredTopic, str, object
            ]
        ] = None,
        reply_topic: Optional[Union[dds.DynamicData.Topic, str, object]] = None,
        datawriter_qos: Optional[dds.DataWriterQos] = None,
        datareader_qos: Optional[dds.DataReaderQos] = None,
        publisher: Optional[dds.Publisher] = None,
        subscriber: Optional[dds.Subscriber] = None,
        on_request_available: Optional[Callable[[object], object]] = None,
    ) -> None:
        super(Replier, self).__init__(
            request_type,
            reply_type,
            participant,
            service_name,
            request_topic,
            reply_topic,
            datawriter_qos,
            datareader_qos,
            publisher,
            subscriber,
            on_request_available,
        )

    async def wait_for_requests_async(
        self, max_wait: dds.Duration, min_count: Optional[int] = 1
    ) -> bool:
        """Wait asynchronously for a minimum number of requests within a timeout period.

        :param max_wait: Maximum time to wait for requests before timing out. .
        :param min_count: Minimum number of requests to receive, default 1.
        :return: Boolean indicating whether min_count requests were received within max_wait time.
        """
        return await _util_async.wait_for_samples_async(
            self._reader,
            min_count,
            max_wait,
            self._waitset,
            self._any_sample_condition,
            self._notread_sample_condition,
        )
