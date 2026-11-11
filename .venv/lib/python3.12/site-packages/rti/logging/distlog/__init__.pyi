import rti.logging.distlog
import typing
import builtins
import rti.connextdds

class LogLevel():
    """
    Members:

      SILENT

      FATAL

      SEVERE

      ERROR

      WARNING

      NOTICE

      INFO

      DEBUG

      TRACE
    """
    def __eq__(self, other: object) -> bool: ...
    def __getstate__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __index__(self) -> int: ...
    def __init__(self, value: int) -> None: ...
    def __int__(self) -> int: ...
    def __ne__(self, other: object) -> bool: ...
    def __repr__(self) -> str: ...
    def __setstate__(self, state: int) -> None: ...
    def __str__(self) -> str: ...
    @builtins.property
    def name(self) -> str:
        """
        :type: str
        """
    @builtins.property
    def value(self) -> int:
        """
        :type: int
        """
    DEBUG: rti.logging.distlog.LogLevel
    ERROR: rti.logging.distlog.LogLevel
    FATAL: rti.logging.distlog.LogLevel
    INFO: rti.logging.distlog.LogLevel
    NOTICE: rti.logging.distlog.LogLevel
    SEVERE: rti.logging.distlog.LogLevel
    SILENT: rti.logging.distlog.LogLevel
    TRACE: rti.logging.distlog.LogLevel
    WARNING: rti.logging.distlog.LogLevel
    __members__: dict
    pass
class Logger():
    @staticmethod
    def debug(message: str) -> None: 
        """
        Log a debug message.
        """
    @staticmethod
    def error(message: str) -> None: 
        """
        Log an error message.
        """
    @staticmethod
    def fatal(message: str) -> None: 
        """
        Log a fatal message.
        """
    @staticmethod
    def filter_level(level: rti.logging.distlog.LogLevel) -> None: 
        """
        The logger filter level.
        """
    @staticmethod
    def finalize() -> None: 
        """
        Destroy the Logger. It should not be accessed after this call.
        """
    @staticmethod
    def info(message: str) -> None: 
        """
        Log an info message.
        """
    @staticmethod
    def init(options: typing.Optional[rti.logging.distlog.LoggerOptions] = None) -> None: 
        """
        Initializes the distributed logger
        """
    @staticmethod
    @typing.overload
    def log(log_level: rti.logging.distlog.LogLevel, message: str) -> None: 
        """
        Log a message with the given log level.
        """
    @staticmethod
    @typing.overload
    def log(log_level: rti.logging.distlog.LogLevel, message: str, category: str) -> None: 
        """
        Log a message with the given log level and category.
        """
    @staticmethod
    @typing.overload
    def log(message_params: rti.logging.distlog.MessageParams) -> None: 
        """
        Log a message with the given message parameters.
        """
    @staticmethod
    def notice(message: str) -> None: 
        """
        Log a notice message.
        """
    @staticmethod
    def print_format(format: rti.connextdds.PrintFormat) -> None: 
        """
        The logger print format.NOTE: This will affect the print format of the associatedDomainParticipant's logger as well.
        """
    @staticmethod
    def severe(message: str) -> None: 
        """
        Log a severe message.
        """
    @staticmethod
    def trace(message: str) -> None: 
        """
        Log a trace message.
        """
    @staticmethod
    def verbosity(category: rti.connextdds.LogCategory, level: rti.connextdds.Verbosity) -> None: 
        """
        The logger's verbosity.NOTE: This will affect the verbosity of the associatedDomainParticipant's logger as well.
        """
    @staticmethod
    def warning(message: str) -> None: 
        """
        Log a warning message.
        """
    pass
class LoggerOptions():
    def __init__(self) -> None: 
        """
        Create a LoggerOptions instance with default settings.
        """
    @builtins.property
    def application_kind(self) -> str:
        """
        The application_kind.

        :type: str
        """
    @application_kind.setter
    def application_kind(self, arg1: str) -> None:
        """
        The application_kind.
        """
    @builtins.property
    def domain_id(self) -> int:
        """
        The domain ID for logging.

        :type: int
        """
    @domain_id.setter
    def domain_id(self, arg1: int) -> None:
        """
        The domain ID for logging.
        """
    @builtins.property
    def echo_to_stdout(self) -> bool:
        """
        Toggle for echo to stdout.

        :type: bool
        """
    @echo_to_stdout.setter
    def echo_to_stdout(self, arg1: bool) -> None:
        """
        Toggle for echo to stdout.
        """
    @builtins.property
    def filter_level(self) -> LogLevel:
        """
        Toggle for log filter level.

        :type: LogLevel
        """
    @filter_level.setter
    def filter_level(self, arg1: LogLevel) -> None:
        """
        Toggle for log filter level.
        """
    @builtins.property
    def log_infrastructure_messages(self) -> bool:
        """
        Toggle for logging infrastructure messages.

        :type: bool
        """
    @log_infrastructure_messages.setter
    def log_infrastructure_messages(self, arg1: bool) -> None:
        """
        Toggle for logging infrastructure messages.
        """
    @builtins.property
    def participant(self) -> typing.Optional[rti.connextdds.DomainParticipant]:
        """
        The DomainParticipant to use for the logger.

        :type: typing.Optional[rti.connextdds.DomainParticipant]
        """
    @participant.setter
    def participant(self, arg1: rti.connextdds.DomainParticipant) -> None:
        """
        The DomainParticipant to use for the logger.
        """
    @builtins.property
    def qos_library(self) -> str:
        """
        The QoS library name.

        :type: str
        """
    @qos_library.setter
    def qos_library(self, arg1: str) -> None:
        """
        The QoS library name.
        """
    @builtins.property
    def qos_profile(self) -> str:
        """
        The QoS profile name.

        :type: str
        """
    @qos_profile.setter
    def qos_profile(self, arg1: str) -> None:
        """
        The QoS profile name.
        """
    @builtins.property
    def queue_size(self) -> int:
        """
        The logger's queue size.

        :type: int
        """
    @queue_size.setter
    def queue_size(self, arg1: int) -> None:
        """
        The logger's queue size.
        """
    @builtins.property
    def remote_administration_enabled(self) -> bool:
        """
        Toggle for remote administration.

        :type: bool
        """
    @remote_administration_enabled.setter
    def remote_administration_enabled(self, arg1: bool) -> None:
        """
        Toggle for remote administration.
        """
    @builtins.property
    def thread_settings(self) -> rti.connextdds.ThreadSettings:
        """
        The settings for the thread handling logging.

        :type: rti.connextdds.ThreadSettings
        """
    @thread_settings.setter
    def thread_settings(self, arg1: rti.connextdds.ThreadSettings) -> None:
        """
        The settings for the thread handling logging.
        """
    pass
class MessageParams():
    def __init__(self, log_level: rti.logging.distlog.LogLevel, message: str, category: str, timestamp: rti.connextdds.Time) -> None: 
        """
        Create MessageParams.
        """
    @builtins.property
    def category(self) -> str:
        """
        The log message category.

        :type: str
        """
    @category.setter
    def category(self, arg1: str) -> None:
        """
        The log message category.
        """
    @builtins.property
    def log_level(self) -> LogLevel:
        """
        The message log level.

        :type: LogLevel
        """
    @log_level.setter
    def log_level(self, arg1: LogLevel) -> None:
        """
        The message log level.
        """
    @builtins.property
    def message(self) -> str:
        """
        The log message.

        :type: str
        """
    @message.setter
    def message(self, arg1: str) -> None:
        """
        The log message.
        """
    @builtins.property
    def timestamp(self) -> rti.connextdds.Time:
        """
        The timestamp of the log message.

        :type: rti.connextdds.Time
        """
    @timestamp.setter
    def timestamp(self, arg1: rti.connextdds.Time) -> None:
        """
        The timestamp of the log message.
        """
    pass
