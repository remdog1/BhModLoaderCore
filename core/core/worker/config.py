import os
from typing import List

from .dataversion import DataClass, DataVariable
from .variables import (DATA_FORMAT_MODLOADER_CORE, DATA_FORMAT_MODLOADER_VERSION,
                        MODLOADER_CACHE_PATH, MODLOADER_CACHE_CORE_FILE)
from .vartypes import ModloaderCoreMods


class ModloaderCoreConfigClass(DataClass):
    DataVariable(DATA_FORMAT_MODLOADER_CORE, 0, "formatVersion")
    formatVersion: int = DATA_FORMAT_MODLOADER_VERSION

    DataVariable(DATA_FORMAT_MODLOADER_CORE, 0, "formatType")
    formatType: str = DATA_FORMAT_MODLOADER_CORE

    DataVariable(formatType, 1, "brawlhallaVersion")
    brawlhallaVersion: str

    DataVariable(formatType, 1, "brawlhallaAirHash")
    brawlhallaAirHash: str

    DataVariable(formatType, 1, "brawlhallaIgnoredPaths")
    brawlhallaIgnoredPaths: List[str]

    DataVariable(formatType, 1, "brawlhallaAllowedPaths")
    brawlhallaAllowedPaths: List[str]

    DataVariable(formatType, 1, "mods")
    mods: List[ModloaderCoreMods]

    DataVariable(formatType, 1, "installedMods")
    installedMods: List[ModloaderCoreMods]

    def __init__(self):
        self.path = os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_CORE_FILE)
        self.loadJsonFile(self.path)

    def save(self):
        self.saveJsonFile(self.path)


ModloaderCoreConfig = ModloaderCoreConfigClass()
