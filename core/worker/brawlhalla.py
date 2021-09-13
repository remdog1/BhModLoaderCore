import os
import re
import sys

from .config import ModloaderCoreConfig

from ..utils.hash import HashFile
from ..ffdec.classes import ArrayList, Configuration, HighlightedTextWriter, ScriptExportMode
from ..swf import Swf

__all__ = ["BRAWLHALLA_PATH", "BRAWLHALLA_SWFS", "BRAWLHALLA_FILES", "BRAWLHALLA_VERSION"]


BRAWLHALLA_PATH = None
BRAWLHALLA_SWFS = {}
BRAWLHALLA_FILES = {}
BRAWLHALLA_VERSION = None


if sys.platform in ["win32", "win64"]:
    import winreg

    brawlhallaFolders = []
    steamHomePath = ""

    for reg in ["SOFTWARE\\WOW6432Node\\Valve\\Steam", "SOFTWARE\\Valve\\Steam"]:
        try:
            steamHomePath = winreg.QueryValueEx(
                winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    reg
                ),
                "InstallPath"
            )[0]
            break
        except FileNotFoundError:
            pass

    if steamHomePath:
        with open(os.path.join(os.path.join(steamHomePath, "steamapps"), "libraryfolders.vdf")) as vdf:
            for path in [*re.findall(r'(?:"\d{1,3}"|"path")\t{2}"(.+)"', vdf.read()), steamHomePath]:
                folder = os.path.join(path.replace("\\\\", "\\"), "steamapps")
                if not os.path.exists(folder):
                    continue
                if "common" in os.listdir(folder) and "Brawlhalla" in os.listdir(os.path.join(folder, "common")):
                    brawlhallaFolders.append(os.path.join(folder, "common", "Brawlhalla"))

        brawlhallaFolders = list({*brawlhallaFolders, *ModloaderCoreConfig.brawlhallaAllowedPaths})

        for folder in brawlhallaFolders:
            if os.path.exists(folder) and "Brawlhalla.exe" in os.listdir(folder) and "BrawlhallaAir.swf" in os.listdir(
                    folder):
                if folder in ModloaderCoreConfig.brawlhallaIgnoredPaths:
                    continue

                BRAWLHALLA_PATH = folder

    del brawlhallaFolders
    del steamHomePath

    if BRAWLHALLA_PATH is None:
        import time
        import psutil

        os.system("start steam://rungameid/291550")

        found = False
        path = None

        i = 0
        while not found and i < 7:
            time.sleep(1)

            for proc in psutil.process_iter():
                try:
                    proc_name = proc.name()
                except psutil.NoSuchProcess:
                    pass
                else:
                    if proc_name == "Brawlhalla.exe":
                        found = True
                        os.system(f'taskkill /pid {proc.pid}')
                        path = proc.cwd()
                        break

            i += 1

        BRAWLHALLA_PATH = path

    if BRAWLHALLA_PATH is None:
        import multiprocessing

        FileExistsError("Brawlhalla not found!")

        if multiprocessing.parent_process() is not None:
            os.kill(multiprocessing.parent_process().pid, 15)
        os.kill(multiprocessing.current_process().pid, 15)

elif sys.platform == "darwin":
    pass

else:
    pass

if BRAWLHALLA_PATH is not None:
    # Search brawlhalla swfs
    for path, _, files in os.walk(BRAWLHALLA_PATH):
        if len(path.replace(BRAWLHALLA_PATH, "").split("\\")) > 2:
            continue

        for file in files:
            if file.endswith(".swf"):
                BRAWLHALLA_SWFS[file] = os.path.join(path, file)

    # Search brawlhalla files
    for path, _, files in os.walk(BRAWLHALLA_PATH):
        for file in files:
            if file.endswith(".mp3") or file.endswith(".png") or file.endswith(".jpg"):
                BRAWLHALLA_FILES[file] = os.path.join(path, file)

    # Get brawlhalla version
    _bhAir = BRAWLHALLA_SWFS.get("BrawlhallaAir.swf", None)

    if _bhAir is not None:
        brawlhallaAirHash = HashFile(_bhAir)

        if brawlhallaAirHash == ModloaderCoreConfig.brawlhallaAirHash:
            BRAWLHALLA_VERSION = ModloaderCoreConfig.brawlhallaVersion

        else:
            brawlhallaAir = Swf(_bhAir)

            for AS3Pack in brawlhallaAir.AS3Packs:
                methodInfos = ArrayList()
                AS3Pack.getMethodInfos(methodInfos)

                abc = AS3Pack.abc
                for methodInfo in methodInfos:
                    bodyIndex = abc.findBodyIndex(methodInfo.getMethodIndex())

                    if bodyIndex != -1:
                        body = abc.bodies.get(bodyIndex)
                        writer = HighlightedTextWriter(Configuration.getCodeFormatting(), True)
                        abc.bodies.get(bodyIndex).getCode().toASMSource(abc, abc.constants,
                                                                        abc.method_info.get(body.method_info),
                                                                        body,
                                                                        ScriptExportMode.PCODE,
                                                                        writer)
                        search = re.findall(r'pushstring "(\d\.\d\d|\d\.\d\d.\d)"', str(writer.toString()))

                        if search:
                            BRAWLHALLA_VERSION = search[0]
                            break

                if BRAWLHALLA_VERSION is not None:
                    ModloaderCoreConfig.brawlhallaVersion = BRAWLHALLA_VERSION
                    ModloaderCoreConfig.brawlhallaAirHash = brawlhallaAirHash
                    ModloaderCoreConfig.save()
                    break

            brawlhallaAir.close()
            del brawlhallaAir

    del _bhAir
