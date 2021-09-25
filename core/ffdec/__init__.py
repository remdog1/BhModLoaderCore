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
        raise ImportError("Java not found!")

jpype.startJVM("-XX:+UseShenandoahGC",
               "-XX:+UnlockExperimentalVMOptions",
               "-XX:ShenandoahUncommitDelay=1000",
               "-XX:ShenandoahGuaranteedGCInterval=10000",
               "-XX:MinHeapFreeRatio=5",
               "-XX:MaxHeapFreeRatio=5",
               "-XX:-AggressiveHeap",
               classpath=[FFDEC_LIB, CMYKJPEG_LIB, JL_LIB], jvmpath=jvmpath)

from .classes import *
