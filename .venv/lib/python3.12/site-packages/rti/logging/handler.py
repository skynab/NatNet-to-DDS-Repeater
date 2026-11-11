# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

from . import distlog as distlog
import logging
import threading

from typing import Optional


class DistlogHandler(logging.Handler):
    _lock = threading.Lock()
    _count = 0
    _levelMap = {
        logging.CRITICAL: distlog.LogLevel.SEVERE,
        logging.ERROR: distlog.LogLevel.ERROR,
        logging.WARNING: distlog.LogLevel.WARNING,
        logging.INFO: distlog.LogLevel.INFO,
        logging.DEBUG: distlog.LogLevel.DEBUG,
    }

    def __init__(self, options: Optional[distlog.LoggerOptions] = None) -> None:
        logging.Handler.__init__(self)
        DistlogHandler._lock.acquire()
        DistlogHandler._count += 1
        distlog.Logger.init(options)
        self._closed = False
        DistlogHandler._lock.release()

    def close(self):
        # type: () -> None
        DistlogHandler._lock.acquire()
        if self._closed:
            raise RuntimeError("Attempted multiple closure of DistlogHandler")
        self._closed = True
        DistlogHandler._count -= 1
        if DistlogHandler._count == 0:
            distlog.Logger.finalize()
        logging.Handler.close(self)
        DistlogHandler._lock.release()

    def emit(self, record):
        # type: (logging.LogRecord) -> None
        level = DistlogHandler._levelMap[record.levelno]
        if hasattr(record, "category"):
            distlog.Logger.log(level, record.getMessage(), record.category)
        else:
            distlog.Logger.log(level, record.getMessage())
