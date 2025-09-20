import os
from typing import Dict, List

from .dataversion import DataClass, DataVariable
from .variables import (DATA_FORMAT_MODLOADER_FILES,
                        DATA_FORMAT_MODLOADER_VERSION,
                        MODLOADER_CACHE_PATH,
                        MODLOADER_CACHE_FILES_FILE,
                        MODLOADER_CACHE_FILES_FOLDER)
from .brawlhalla import BRAWLHALLA_FILES
from .basedispatch import SendNotification

from ..utils.hash import HashFile, HashFromBytes
from ..notifications import NotificationType


class GameFilesData(DataClass):
    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "formatVersion")
    formatVersion: int = DATA_FORMAT_MODLOADER_VERSION

    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "formatType")
    formatType: str = DATA_FORMAT_MODLOADER_FILES

    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "origFiles")
    origFiles: Dict[str, str]   # {fileName: origFIleHash}

    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "modFiles")
    modFiles: Dict[str, str]    # {fileName: fileHash}

    DataVariable(DATA_FORMAT_MODLOADER_FILES, 0, "modifiedFilesMap")
    modifiedFilesMap: Dict[str, str]    # {fileName: modHash}

    def loadData(self):
        self.loadJsonFile(os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_FILES_FILE))

    def saveData(self):
        self.saveJsonFile(os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_FILES_FILE))


class GameFilesClass(GameFilesData):
    def __init__(self):
        self.loadData()
        self.origPreviewsPath = os.path.join(MODLOADER_CACHE_PATH, MODLOADER_CACHE_FILES_FOLDER)

        if not os.path.exists(self.origPreviewsPath):
            os.mkdir(self.origPreviewsPath)

    def installFile(self, fileName: str, modFileContent: bytes, modHash: str):
        #print("Install file", fileName)
        SendNotification(NotificationType.InstallingModFile, modHash, fileName)

        if fileName in BRAWLHALLA_FILES:
            with open(BRAWLHALLA_FILES[fileName], "rb") as file:
                origFileContent = file.read()

            origFileHash = HashFromBytes(origFileContent)
            modFileHash = HashFromBytes(modFileContent)

            copyOrigFile = True

            if fileName not in self.origFiles:
                #print("Кеширование файла", fileName)
                #SendNotification(NotificationType.InstallingModFileCache, modHash, fileName)
                self.origFiles[fileName] = origFileHash
            elif fileName not in self.modFiles and self.origFiles[fileName] != origFileHash:
                #print("Перезапись кэша файла", fileName)
                #SendNotification(NotificationType.InstallingModFileCache, modHash, fileName)
                self.origFiles[fileName] = origFileHash
            elif fileName in self.modFiles and origFileHash not in (self.origFiles[fileName], self.modFiles[fileName]):
                #print("Перезапись кэша файла", fileName)
                #SendNotification(NotificationType.InstallingModFileCache, modHash, fileName)
                self.origFiles[fileName] = origFileHash
            else:
                copyOrigFile = False

            if copyOrigFile:
                #print("Копирование оригинального файла")
                SendNotification(NotificationType.InstallingModFileCache, modHash, fileName)
                with open(os.path.join(self.origPreviewsPath, fileName), "wb") as copyFile:
                    copyFile.write(origFileContent)

            if origFileHash != modFileHash:
                #print("Замена оригинального файла")
                with open(BRAWLHALLA_FILES[fileName], "wb") as modFile:
                    modFile.write(modFileContent)

            self.modFiles[fileName] = modFileHash
            self.modifiedFilesMap[fileName] = modHash

            self.saveData()

        pass

    def repairFile(self, fileName: str):
        if fileName in self.origFiles:
            with open(os.path.join(self.origPreviewsPath, fileName), "rb") as copyFile:
                origFileContent = copyFile.read()

            with open(BRAWLHALLA_FILES[fileName], "wb") as file:
                file.write(origFileContent)

            self.modFiles.pop(fileName, None)
            self.modifiedFilesMap.pop(fileName, None)

    def uninstallMod(self, modHash: str):
        for fileName, fileModHash in self.modifiedFilesMap.copy().items():
            if fileModHash == modHash:
                #print("Восстановление файла", fileName)
                SendNotification(NotificationType.UninstallingModFile, modHash, fileName)
                self.repairFile(fileName)

        self.saveData()

    def getModConflict(self, files: List[str], modHash: str):
        conflictMods = set()

        for file in files:
            if file in self.modifiedFilesMap:
                conflictMods.add(self.modifiedFilesMap[file])

        return list(conflictMods)


GameFiles = GameFilesClass()

