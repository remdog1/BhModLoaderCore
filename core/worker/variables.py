import os
import sys

CORE_VERSION = "1.0.0"

MODS_PATH = []
MODS_SOURCES_PATH = []

MOD_FILE_FORMAT = "bmod"

METADATA_FORMAT_VERSION = 2
METADATA_FORMAT_MOD = "mod"
METADATA_FORMAT_GAME = "game"
METADATA_FORMAT_CACHE_MOD = "cache_mod"
METADATA_FORMAT_CACHE_MODS_HASH_SUM = "cache_hash_sum_mods"
METADATA_CACHE_MOD_FILE = "mod.json"
METADATA_CACHE_MODS_HASH_SUM_FILE = "mods.json"
METADATA_CACHE_MOD_PREVIEWS_FOLDER = "Previews"


DATA_FORMAT_MODLOADER_VERSION = 1
DATA_FORMAT_MODLOADER_CORE = "modloader_core"
DATA_FORMAT_MODLOADER_FILES = "modloader_files"

MODS_SOURCES_CACHE_FILE = "_cache.json"
MODS_SOURCES_CACHE_PREVIEW = "_previews"


MODLOADER_CACHE_CORE_FILE = "core.json"
MODLOADER_CACHE_FILES_FILE = "files.json"
MODLOADER_CACHE_FILES_FOLDER = "OriginalFiles"
MODLOADER_CACHE_MODS_FOLDER = "Mods"

MODLOADER_CACHE_FOLDER = "BModloader"
if sys.platform in ["win32", "win64"]:
    appdata = os.getenv("APPDATA")
    if appdata:
        MODLOADER_CACHE_PATH = os.path.join(appdata, MODLOADER_CACHE_FOLDER)
    else:
        # Fallback to local directory if APPDATA environment variable is not available
        MODLOADER_CACHE_PATH = os.path.join(os.getcwd(), "BModloaderCache")
elif sys.platform == "darwin":
    MODLOADER_CACHE_PATH = os.path.join(os.getcwd(), "appconfig")
else:
    MODLOADER_CACHE_PATH = os.path.join(os.getcwd(), "BModloaderCache")

if not os.path.exists(MODLOADER_CACHE_PATH):
    os.makedirs(MODLOADER_CACHE_PATH)


def CheckExists(path, makeIfNotExists=False):
    if path and not os.path.exists(path) and makeIfNotExists:
        os.makedirs(path)


def SetModsPath(path):
    for v in MODS_PATH:
        MODS_PATH.remove(v)

    MODS_PATH.append(path)

    CheckExists(path, True)


def SetModsSourcesPath(path):
    for v in MODS_SOURCES_PATH:
        MODS_SOURCES_PATH.remove(v)

    MODS_SOURCES_PATH.append(path)

    CheckExists(path, True)

