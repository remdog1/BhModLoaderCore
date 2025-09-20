
import os
import traceback
from typing import List, Union

from .variables import (MODS_PATH,
                        MOD_FILE_FORMAT,
                        MODS_SOURCES_PATH,
                        MODLOADER_CACHE_PATH,
                        MODLOADER_CACHE_MODS_FOLDER,
                        CheckExists)
from .mod import ModClass, ModSource, ModsHashSumCache
from .config import ModloaderCoreConfig
from .basedispatch import SendNotification
from ..notifications import NotificationType


class ModLoaderClass:
    modsSources: List[ModSource] = []
    modsClasses: List[ModClass] = []
    modsGhosts: list = []

    def __init__(self):
        self.config = ModloaderCoreConfig
        self.modsCachePath = os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_MODS_FOLDER)
        if not os.path.exists(self.modsCachePath):
            os.mkdir(self.modsCachePath)

    def reload(self):
        self.reloadMods()
        self.reloadModsSources()

    def clear(self):
        self.modsSources = []
        self.modsClasses = []
        self.modsGhosts = []

    def getModsData(self):
        return [{**mod.getDict(ignoredVars=["swfs", "files", "previewsIds", "formatType", "formatVersion"]),
                 "previewsPaths": mod.getPreviewsPaths(), "currentGameVersion": self.config.brawlhallaVersion}
                for mod in self.modsClasses]

    def getModsSourcesData(self):
        return [{**modSources.getDict(ignoredVars=["swfs", "files", "previewsIds", "formatType", "formatVersion"]),
                 "previewsPaths": modSources.getPreviewsPaths(), "currentGameVersion": self.config.brawlhallaVersion,
                 "modSourcesPath": modSources.modSourcesPath}
                for modSources in self.modsSources]

    def loadMods(self):
        modsHashes = []
        if MODS_PATH:
            modsPath = MODS_PATH[0]
            CheckExists(modsPath, True)

            for modFile in os.listdir(modsPath):
                modPath = os.path.join(modsPath, modFile)
                if modFile.endswith(f".{MOD_FILE_FORMAT}") and os.path.isfile(modPath):
                    try:
                        modClass = ModClass(modPath=modPath, modsCachePath=self.modsCachePath)
                        # Not load duplicate
                        if modClass.hash not in modsHashes:
                            modsHashes.append(modClass.hash)
                            self.modsClasses.append(modClass)
                    except:
                        traceback.print_exc()

        cacheHashes = ModsHashSumCache(self.modsCachePath)
        for modHash in cacheHashes.hashes.values():
            if modHash not in modsHashes:
                try:
                    modClass = ModClass(modsCachePath=self.modsCachePath, modHash=modHash)
                    self.modsClasses.append(modClass)
                except:
                    pass

    def reloadMods(self):
        self.modsClasses = []
        self.loadMods()

    def loadModsSources(self):
        modsSourcesHashes = []
        if MODS_SOURCES_PATH:
            modsSourcesPath = MODS_SOURCES_PATH[0]
            CheckExists(modsSourcesPath, True)

            for modSourcesFolder in os.listdir(modsSourcesPath):
                modSourcesPath = os.path.join(modsSourcesPath, modSourcesFolder)
                if os.path.isdir(modSourcesPath) and not modSourcesFolder.startswith("__"):
                    modSource = ModSource(modSourcesPath)
                    # Not load duplicate
                    if modSource.hash not in modsSourcesHashes:
                        modsSourcesHashes.append(modSource.hash)
                        self.modsSources.append(modSource)

    def reloadModsSources(self):
        self.modsSources: List[ModSource] = []
        self.loadModsSources()

    def getModByHash(self, hash: str) -> Union[ModClass, None]:
        for mod in self.modsClasses:
            if mod.hash == hash:
                return mod

        return None

    def getModSourcesByHash(self, hash: str) -> Union[ModSource, None]:
        for modSources in self.modsSources:
            if modSources.hash == hash:
                return modSources

        return None

    def createModSource(self, folderName: str) -> Union[ModSource, None]:
        path = os.path.join(MODS_SOURCES_PATH[0], folderName)
        if os.path.exists(path):
            return None
        else:
            os.mkdir(path)
            modSource = ModSource(path)
            self.modsSources.append(modSource)
            return modSource

    def load(self):
        self.loadMods()
        self.loadModsSources()


ModLoader = ModLoaderClass()
