import os
import sys
import jpype

__all__ = []

FFDEC_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), "ffdec_lib.jar"))
CMYKJPEG_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), "cmykjpeg.jar"))
JL_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), "jl1.0.1.jar"))

assert os.path.exists(FFDEC_LIB), "ffdec_lib.jar doesn't exist"
assert os.path.exists(CMYKJPEG_LIB), "cmykjpeg.jar doesn't exist"
assert os.path.exists(JL_LIB), "jl1.0.1.jar doesn't exist"

if sys.platform == "darwin":
    jvmpath = "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/lib/jli/libjli.dylib"
else:
    try:
        jvmpath = jpype._jvmfinder.getDefaultJVMPath()
    except jpype._jvmfinder.JVMNotFoundException:
        jvmpath = ""

        try:
            import win32api
            import win32con
            win32api.MessageBox(None, "Java not found!", "ModLoader Core",
                                win32con.MB_ICONERROR | win32con.MB_OK | win32con.MB_DEFBUTTON1)
        except ImportError:
            print("Java not found!")

jpype.startJVM(classpath=[FFDEC_LIB, CMYKJPEG_LIB, JL_LIB], jvmpath=jvmpath)

from .classes import *

# import multiprocessing
# process = multiprocessing.current_process()
# if process._parent_pid is not None:
#    print("Parent process:", process._parent_name)
