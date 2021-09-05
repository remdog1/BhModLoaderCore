import os
import sys

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
    MODLOADER_CACHE_PATH = os.path.join(os.getenv("APPDATA"), MODLOADER_CACHE_FOLDER)
elif sys.platform == "darwin":
    MODLOADER_CACHE_PATH = os.path.join(os.getcwd(), "appconfig")
else:
    MODLOADER_CACHE_PATH = ""

if not os.path.exists(MODLOADER_CACHE_PATH):
    os.mkdir(MODLOADER_CACHE_PATH)


def SetModsPath(path):
    for v in MODS_PATH:
        MODS_PATH.remove(v)

    MODS_PATH.append(path)

    if path and not os.path.exists(path):
        os.makedirs(path)


def SetModsSourcesPath(path):
    for v in MODS_SOURCES_PATH:
        MODS_SOURCES_PATH.remove(v)

    MODS_SOURCES_PATH.append(path)

    if path and not os.path.exists(path):
        os.makedirs(path)
