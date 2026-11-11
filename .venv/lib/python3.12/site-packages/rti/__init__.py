# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

import platform

if platform.system() == "Windows":
    import os

    pkg_dir = os.path.dirname(os.path.realpath(__file__))
    os.environ.setdefault("PATH", "")
    os.environ["PATH"] = pkg_dir + os.pathsep + os.environ["PATH"]
