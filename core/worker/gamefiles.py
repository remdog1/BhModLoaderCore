import os
from typing import Dict, List

from .dataversion import DataClass, DataVariable
from .variables import (DATA_FORMAT_MODLOADER_FILES,
                        DATA_FORMAT_MODLOADER_VERSION,
                        MODLOADER_CACHE_PATH,
                        MODLOADER_CACHE_FILES_FILE,
                        MODLOADER_CACHE_FILES_FOLDER)
from .brawlhalla import BRAWLHALLA_FILES, BRAWLHALLA_SWFS
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
        SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Installing file: {fileName}")
        SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: File size: {len(modFileContent)} bytes")
        SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Mod hash: {modHash}")
        
        SendNotification(NotificationType.InstallingModFile, modHash, fileName)

        # Check if file is in BRAWLHALLA_FILES or BRAWLHALLA_SWFS (for SWF files)
        target_path = None
        if fileName in BRAWLHALLA_FILES:
            target_path = BRAWLHALLA_FILES[fileName]
            SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: File found in BRAWLHALLA_FILES: {fileName}")
        elif fileName in BRAWLHALLA_SWFS:
            target_path = BRAWLHALLA_SWFS[fileName]
            SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: File found in BRAWLHALLA_SWFS: {fileName}")
        
        if target_path:
            SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Target path: {target_path}")
            
            with open(target_path, "rb") as file:
                origFileContent = file.read()

            origFileHash = HashFromBytes(origFileContent)
            modFileHash = HashFromBytes(modFileContent)
            
            SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Original file hash: {origFileHash}")
            SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Mod file hash: {modFileHash}")
            SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Hashes match: {origFileHash == modFileHash}")

            copyOrigFile = True

            if fileName not in self.origFiles:
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: File not in origFiles cache - caching")
                self.origFiles[fileName] = origFileHash
            elif fileName not in self.modFiles and self.origFiles[fileName] != origFileHash:
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Original file changed - updating cache")
                self.origFiles[fileName] = origFileHash
            elif fileName in self.modFiles and origFileHash not in (self.origFiles[fileName], self.modFiles[fileName]):
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: File modified - updating cache")
                self.origFiles[fileName] = origFileHash
            else:
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: No cache update needed")
                copyOrigFile = False

            if copyOrigFile:
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Copying original file to cache")
                SendNotification(NotificationType.InstallingModFileCache, modHash, fileName)
                # Use basename for cache file to avoid directory structure issues
                cache_filename = os.path.basename(fileName)
                cache_path = os.path.join(self.origPreviewsPath, cache_filename)
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Cache path: {cache_path}")
                
                with open(cache_path, "wb") as copyFile:
                    copyFile.write(origFileContent)
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Original file cached successfully")

            if origFileHash != modFileHash:
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Replacing original file with mod file")
                with open(target_path, "wb") as modFile:
                    modFile.write(modFileContent)
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: File replaced successfully")
            else:
                SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: File unchanged - no replacement needed")

            self.modFiles[fileName] = modFileHash
            self.modifiedFilesMap[fileName] = modHash
            
            SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Updated mod tracking - modFiles: {self.modFiles.get(fileName)}, modifiedFilesMap: {self.modifiedFilesMap.get(fileName)}")

            self.saveData()
            SendNotification(NotificationType.Debug, f"🔧 GAMEFILES: Installation completed for: {fileName}")
        else:
            SendNotification(NotificationType.Debug, f"❌ GAMEFILES: File not found in BRAWLHALLA_FILES or BRAWLHALLA_SWFS: {fileName}")
            SendNotification(NotificationType.Debug, f"❌ GAMEFILES: Available files: {list(BRAWLHALLA_FILES.keys())[:10]}...")
            SendNotification(NotificationType.Debug, f"❌ GAMEFILES: Available SWF files: {list(BRAWLHALLA_SWFS.keys())[:10]}...")

        pass

    def repairFile(self, fileName: str):
        if fileName in self.origFiles:
            # Use basename for cache file lookup
            cache_filename = os.path.basename(fileName)
            with open(os.path.join(self.origPreviewsPath, cache_filename), "rb") as copyFile:
                origFileContent = copyFile.read()

            # Check if file is in BRAWLHALLA_FILES or BRAWLHALLA_SWFS (for SWF files)
            target_path = None
            if fileName in BRAWLHALLA_FILES:
                target_path = BRAWLHALLA_FILES[fileName]
            elif fileName in BRAWLHALLA_SWFS:
                target_path = BRAWLHALLA_SWFS[fileName]
            
            if target_path:
                with open(target_path, "wb") as file:
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

