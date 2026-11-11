# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

import sys

# The code requires a few functions in asyncio and typing that are new in 3.7/8
if sys.version_info < (3, 8):
    raise ImportError("rti.asyncio requires Python 3.8 or newer")

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Optional, Union, get_type_hints, get_origin, get_args

import rti.connextdds as dds


class _WaitSetAsyncDispatcher:
    def __init__(self):
        self.waitset = dds._FastWaitSet()
        self.cancel_condition = dds.GuardCondition()
        self.run_task = None
        self.finish_event = asyncio.Event()
        self.cancel_token = None
        self.running = False

    class CancelToken:
        def __init__(
            self,
            task: asyncio.Task,
            cancel_condition: dds.GuardCondition,
            finish_event: asyncio.Event,
        ):
            self._task = task
            self._cancel_condition = cancel_condition
            self._finish_event = finish_event

        async def cancel(self):
            # Wake up the waitset in _run_loop so it can exit
            self._cancel_condition.trigger_value = True
            # Await until _run_loop ends
            await self._finish_event.wait()

    async def _run_loop(self):
        try:
            while not self.cancel_condition.trigger_value:
                # Wait runs in an executor thread
                await self.waitset.wait_async()
                # Dispatch runs in the asyncio loop thread. This is required
                # for the asyncio.Events being awaited to wake up (see
                # condition_handler() in wait(), below).
                self.waitset.dispatch()
            self.finish_event.set()
        except asyncio.CancelledError:
            # Let the wait_async() operation end
            self.cancel_condition.trigger_value = True
        finally:
            self.running = False
            self.waitset.get_waitset().detach_all()

    def run(self) -> CancelToken:
        self.running = True
        self.waitset.attach_condition(self.cancel_condition)

        impl_task = asyncio.create_task(self._run_loop())
        self.run_task = _WaitSetAsyncDispatcher.CancelToken(
            impl_task, self.cancel_condition, self.finish_event
        )
        self.cancel_token = self.run_task
        return self.run_task

    async def close(self):
        if self.cancel_token is not None:
            await self.cancel_token.cancel()

    class WaitToken:
        def __init__(self, condition: dds.ReadCondition):
            self.condition = condition

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.condition.reset_handler()

    def register(self, condition: dds.ReadCondition) -> WaitToken:
        return _WaitSetAsyncDispatcher.WaitToken(condition)

    async def wait(self, token: WaitToken):
        if token.condition.trigger_value:
            return  # No need to wait

        token.condition.reset_handler()
        wait_event = asyncio.Event()

        def condition_handler():
            wait_event.set()

        token.condition.set_handler_no_args(condition_handler)
        self.waitset.attach_condition(token.condition)

        await wait_event.wait()

    async def take_data(self, reader: dds.DataReader, condition: dds.Condition):
        with self.register(condition) as wait_token:
            try:
                await self.wait(wait_token)
                while True:
                    for data in reader.take_data():
                        yield data
                    await self.wait(wait_token)
            except asyncio.CancelledError:
                self.waitset.detach_condition(wait_token.condition)
                raise

    async def take(self, reader: dds.DataReader, condition: dds.Condition):
        with self.register(condition) as wait_token:
            try:
                await self.wait(wait_token)
                while True:
                    for sample in reader.take():
                        yield sample
                    await self.wait(wait_token)
            except asyncio.CancelledError:
                self.waitset.detach_condition(wait_token.condition)
                raise


_DEFAULT_DISPATCHER = None


def _get_default_dispatcher() -> _WaitSetAsyncDispatcher:
    global _DEFAULT_DISPATCHER
    if _DEFAULT_DISPATCHER is None:
        _DEFAULT_DISPATCHER = _WaitSetAsyncDispatcher()
    if not _DEFAULT_DISPATCHER.running:
        _DEFAULT_DISPATCHER.run()
    return _DEFAULT_DISPATCHER


def _take_data_async(
    reader: dds.DataReader, condition: Optional[dds.ReadCondition] = None
):
    dispatcher = _get_default_dispatcher()
    if condition is None:
        return dispatcher.take_data(
            reader, condition=dds.ReadCondition(reader, dds.DataState.any)
        )
    else:
        return dispatcher.take_data(
            reader.select().condition(condition), condition=condition
        )


def _take_async(reader: dds.DataReader, condition: Optional[dds.ReadCondition] = None):
    dispatcher = _get_default_dispatcher()
    if condition is None:
        return dispatcher.take(
            reader, condition=dds.ReadCondition(reader, dds.DataState.any)
        )
    else:
        return dispatcher.take(
            reader.select().condition(condition), condition=condition
        )


# Inject async functions to DataReader
dds.DataReader.take_data_async = _take_data_async
dds.DataReader.take_async = _take_async
dds.DynamicData.DataReader.take_data_async = _take_data_async
dds.DynamicData.DataReader.take_async = _take_async


@dataclass
class _DecoratedSubscription:
    topic_name: str
    data_type: type
    func: Any
    needs_sample_info: bool = False
    qos_profile: Optional[str] = None


class Application:
    """An rti.asyncio.Application provides an easy way to subscribe
    to topics by simply decorating async functions to receive topic updates.

    To use this class:

    1. Create an ``app`` instance of this class (typically one per application)
    2. For each topic you want to subscribe to decorate a function with ``@app.subscribe()``
    3. Run the application, typically with ``rti.asyncio.run(app.run(domain_id))``

    For example:

    .. code-block:: python

        app = rti.asyncio.Application()

        @app.subscribe(topic_name="Sensor Temperature")
        async def on_sensor_temperature(data: Temperature):
            print(data)

        @app.subscribe(topic_name="Alerts")
        async def on_alert(data: Alert):
            print(data)

        rti.asyncio.run(app.run(domain_id=0))

    """

    def __init__(self) -> None:
        self._subscriptions = []
        self.participant: Optional[dds.DomainParticipant] = None

    def subscribe(self, topic_name: str, qos_profile: Optional[str] = None):
        """Decorator for a function that will receive samples of the given topic.

        The decorated function must meet the following requirements:

        - It must be ``async``.
        - It must have at least one argument.
        - The first argument must have a type annotation that corresponds to the type of the topic.

        The function may have an optional second argument with the type annotation
        ``dds.SampleInfo``.

        The decorator receives the topic name and an optional QoS profile name.
        The QoS profile name is used to configure the DataReader and Subscriber QoS.

        Example:

        .. code-block:: python

            @app.subscribe(topic_name="MyTopic", qos_profile="my_library::my_profile")
            async def on_my_topic(data: MyType):
                print(data)

        Decorating a function has the following effect when ``run()`` is called:

        - A ``dds.Topic`` with name ``"MyTopic"`` and type ``MyType`` is created.
          If one already exists and the type is the same, it is re-used. If the type
          is different, an exception is raised.

        - A ``dds.DataReader`` is created for the topic. If a QoS profile is provided,
          the profile is loaded and used to configure the DataReader and Subscriber.

        - The decorated function is called with each data sample received by the
          DataReader.

        - If the function has a second argument with the type ``dds.SampleInfo``, the
          sample meta-data is also passed to the function. For updates with
          meta-data only (e.g. when an instance is disposed), the first argument
          is ``None``.

        """

        def helper(func):
            data_type = self._get_first_arg_type(func)
            needs_sample_info = self._has_sample_info_argument(func)
            self._subscriptions.append(
                _DecoratedSubscription(
                    topic_name,
                    data_type,
                    func,
                    needs_sample_info=needs_sample_info,
                    qos_profile=qos_profile,
                )
            )
            return func

        return helper

    async def run(
        self,
        domain_id: Union[int, dds.DomainParticipant] = 0,
        qos_file: Optional[str] = None,
    ):
        """Start all subscriptions and start notifying decorated functions.

        This function creates a ``dds.DomainParticipant`` with the given domain_id
        or uses an existing participant if one is provided. It then creates
        a DataReader for each function that was decorated with ``@app.subscribe``.

        The optional ``qos_file`` argument loads an XML file used to look up
        any QoS profiles specified in the ``@app.subscribe`` decorator. By
        default the default *Connext* methods to look for profiles are used,
        including the ``<working directory>/USER_QOS_PROFILES.xml`` file.

        The simplest way to run this method is with ``rti.asyncio.run``:

        .. code-block:: python

            if __name__ == "__main__":
                rti.asyncio.run(app.run(domain_id))

        To stop the application (and all subscriptions), run as a task and
        cancel it when needed:

        .. code-block:: python

            async def main():
                task = asyncio.create_task(app.run(domain_id))
                # subscriptions are running ...
                task.cancel()
                await task

            if __name__ == "__main__":
                rti.asyncio.run(main())

        """

        if qos_file:
            self.qos_provider = dds.QosProvider(qos_file)
        else:
            self.qos_provider = dds.QosProvider.default

        participant = dds.DomainParticipant(domain_id)
        handlers = self._create_subscriptions(participant)
        self.participant = participant
        try:
            await asyncio.gather(*handlers)
        except asyncio.CancelledError:
            pass  # cancellation is the normal way to stop

    def _get_first_arg_type(self, func):
        """Given a function ``def foo(x: Bar, ...)`` return ``Bar``"""

        signature = inspect.signature(func)
        if not signature.parameters:
            raise ValueError("The function has no arguments.")

        param_iter = iter(signature.parameters)
        first_arg_name = next(param_iter)

        type_hints = get_type_hints(func)
        if first_arg_name not in type_hints:
            raise ValueError(
                f"The first argument '{first_arg_name}' must have a type annotation that corresponds to the type of the topic."
            )

        # the type can be `Foo` or `Optional[Foo]`
        arg_type = type_hints[first_arg_name]
        if get_origin(arg_type):
            arg_type = get_args(arg_type)[0]

        return arg_type

    @staticmethod
    def _log_warning(func_name: str, e: Exception):
        msg = f"Exception in {func_name} while processing a data sample: {e}"
        dds.Logger.instance._log_dds_warning(msg)

    def _has_sample_info_argument(self, func) -> bool:
        """Returns True if the second argument of the function exists and has the `dds.SampleInfo` type annotation"""

        signature = inspect.signature(func)
        if len(signature.parameters) < 2:
            return False

        # allow methods `def foo(self, arg)` and free functions `def foo(arg)`
        param_iter = iter(signature.parameters)
        next(param_iter)
        second_arg_name = next(param_iter)

        type_hints = get_type_hints(func)
        return type_hints.get(second_arg_name) == dds.SampleInfo

    def _create_handler(self, reader: dds.DataReader, needs_info: bool, func):
        if not needs_info:

            async def handler():
                try:
                    async for sample in reader.take_data_async():
                        try:
                            await func(sample)
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            Application._log_warning(func.__name__, e)
                except asyncio.CancelledError:
                    pass  # cancellation is the normal way to stop the handler

            return handler

        else:

            async def handler():
                try:
                    async for sample, info in reader.take_async():
                        try:
                            await func(sample, info)
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            Application._log_warning(func.__name__, e)
                except asyncio.CancelledError:
                    pass  # cancellation is the normal way to stop the handler

            return handler

    def _create_subscriptions(self, participant: dds.DomainParticipant) -> None:
        readers = []
        for sub in self._subscriptions:
            topic = dds.Topic.find(participant, sub.topic_name)
            if topic:
                if topic.type is not sub.data_type:
                    raise ValueError(
                        f"The topic '{sub.topic_name}' is already registered with a different type."
                    )
            else:
                topic = dds.Topic(participant, sub.topic_name, sub.data_type)

            if sub.qos_profile:
                reader_qos = self.qos_provider.datareader_qos_from_profile(
                    sub.qos_profile
                )
                subscriber_qos = self.qos_provider.subscriber_qos_from_profile(
                    sub.qos_profile
                )
                if subscriber_qos != participant.default_subscriber_qos:
                    # We need to create a subscriber because it has specific QoS
                    subscriber = dds.Subscriber(participant, qos=subscriber_qos)
                else:
                    subscriber = participant.implicit_subscriber
                reader = dds.DataReader(subscriber, topic, reader_qos)
            else:
                reader = dds.DataReader(topic)

            readers.append(reader)

        # Create the handlers only after all readers have been created
        # successfully to avoid leaving unawaited coroutines
        handlers = [
            self._create_handler(reader, sub.needs_sample_info, sub.func)()
            for sub, reader in zip(self._subscriptions, readers)
        ]

        return handlers


async def close():
    global _DEFAULT_DISPATCHER
    if _DEFAULT_DISPATCHER is not None:
        await _DEFAULT_DISPATCHER.close()
        _DEFAULT_DISPATCHER = None


def run(coroutine):
    """Uses the current event loop to run the given coroutine and waits until it
    finishes. If there is no current running event loop, a new one is created.
    When it ends, it cleans up global resources.
    """

    async def run_and_close():
        try:
            await coroutine
        finally:
            await close()

    asyncio.run(run_and_close())
