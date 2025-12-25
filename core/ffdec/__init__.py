import os
import sys
import jpype

__all__ = []

# Handle PyInstaller frozen executable paths
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    # __file__ works in both frozen and non-frozen modes
    # In frozen mode, PyInstaller sets __file__ to the correct path in the bundle
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

PLAYERGLOBAL = resource_path("playerglobal32_0.swc")
FFDEC_LIB = resource_path("ffdec_lib.jar")
CMYKJPEG_LIB = resource_path("cmykjpeg.jar")
JL_LIB = resource_path("jl1.0.1.jar")

assert os.path.exists(FFDEC_LIB), "ffdec_lib.jar doesn't exist"
assert os.path.exists(CMYKJPEG_LIB), "cmykjpeg.jar doesn't exist"
assert os.path.exists(JL_LIB), "jl1.0.1.jar doesn't exist"

jvmpath = None

if sys.platform.startswith("win"):
    try:
        jvmpath = jpype._jvmfinder.getDefaultJVMPath()
    except jpype._jvmfinder.JVMNotFoundException:
        pass

    # Handle PyInstaller frozen executable paths for flashlib
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        flashlibFolder = os.path.join(base_path, "tools", "ffdec", "flashlib")
    else:
        flashlibFolder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tools", "ffdec", "flashlib"))
    flashlibFile = os.path.join(flashlibFolder, "playerglobal32_0.swc")

    if not os.path.exists(flashlibFile):
        if not os.path.exists(flashlibFolder):
            os.makedirs(flashlibFolder, exist_ok=True)

        with open(PLAYERGLOBAL, "rb") as orig:
            with open(flashlibFile, "wb") as new:
                new.write(orig.read())

elif sys.platform == "darwin":
    jvmpath = "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/lib/jli/libjli.dylib"

else:
    pass

if jvmpath is None:
    raise ImportError("Java not found!")

# Start JVM with increased heap size to handle large SWF files
# -Xmx2048m: Maximum heap size of 2GB (increased from 512MB)
# -Xms256m: Initial heap size of 256MB (increased from 32MB)
# This prevents OutOfMemoryError when processing large mods or multiple mods
if not jpype.isJVMStarted():
    try:
        jpype.startJVM(jvmpath, "-Xmx2048m", "-Xms256m", classpath=[FFDEC_LIB, CMYKJPEG_LIB, JL_LIB])
    except Exception as e:
        # If starting with 2GB fails (e.g., system doesn't have enough RAM), try 1GB
        if "OutOfMemoryError" in str(e) or "could not reserve enough space" in str(e).lower():
            try:
                jpype.startJVM(jvmpath, "-Xmx1024m", "-Xms128m", classpath=[FFDEC_LIB, CMYKJPEG_LIB, JL_LIB])
            except Exception as e2:
                # Last resort: use original smaller size
                jpype.startJVM(jvmpath, "-Xmx512m", "-Xms32m", classpath=[FFDEC_LIB, CMYKJPEG_LIB, JL_LIB])
        else:
            raise



from .classes import *
