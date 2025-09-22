import os
import re
import shutil
import threading
import time
import json
from typing import List, Dict, Tuple, Union

from .vartypes import ModDataSwfsTyped
from .variables import (MODS_PATH,
                        MODS_SOURCES_PATH,
                        MOD_FILE_FORMAT,
                        METADATA_FORMAT_MOD,
                        METADATA_FORMAT_CACHE_MOD,
                        METADATA_FORMAT_VERSION,
                        METADATA_FORMAT_CACHE_MODS_HASH_SUM,
                        METADATA_CACHE_MODS_HASH_SUM_FILE,
                        METADATA_CACHE_MOD_PREVIEWS_FOLDER,
                        METADATA_CACHE_MOD_FILE,
                        MODS_SOURCES_CACHE_FILE,
                        MODS_SOURCES_CACHE_PREVIEW,
                        MODLOADER_CACHE_PATH)
from .dataversion import DataClass, DataVariable
from .gameswf import GetGameFileClass
from .gamefiles import GameFiles
from .brawlhalla import BRAWLHALLA_SWFS, BRAWLHALLA_FILES, BRAWLHALLA_VERSION
from .basedispatch import SendNotification
from .bnkhandler import bnk_handler

from ..utils.hash import RandomHash, HashFile

from ..swf.swf import Swf, GetElementId, SetElementId, GetShapeBitmapId, SetShapeBitmapId
from ..ffdec.classes import (CSMTextSettingsTag,
                             DefineFontNameTag,
                             DefineFontAlignZonesTag,
                             DefineBitsLosslessTags,
                             DefineFontTags,
                             DefineEditTextTag,
                             DefineTextTag,
                             DefineSoundTag,
                             DefineShapeTags,
                             DefineSpriteTag,
                             PlaceObject2Tag,
                             PlaceObject3Tag)
from ..notifications import NotificationType

__all__ = ["BaseModClass", "ModSource", "ModClass"]


LOCK = threading.Lock()


class BaseModClass(DataClass):
    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 0, "formatVersion")
    formatVersion: int = METADATA_FORMAT_VERSION

    DataVariable(METADATA_FORMAT_MOD, 0, "formatType")
    formatType: str = METADATA_FORMAT_MOD

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "gameVersion")
    gameVersion: str

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "name")
    name: str

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "author")
    author: str

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "version")
    version: str

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "description")
    description: str

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "tags")
    tags: List[str]

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "previewsIds")
    previewsIds: Dict[int, str]

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "hash")
    hash: str

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "swfs")
    swfs: Dict[str, ModDataSwfsTyped]

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "files")
    files: Dict[int, str]

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "authorId")
    authorId: int

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "modId")
    modId: int

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "platform")
    platform: str

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 2, "modUrl")
    modUrl: str

    def loadModData(self):
        pass

    def getGameVersion(self):
        return self.gameVersion

    def getName(self):
        return self.name

    def getAuthor(self):
        return self.author

    def getVersion(self):
        return self.version

    def getDescription(self):
        return self.description

    def getTags(self):
        return self.tags

    def getPreviewsPaths(self) -> List[str]:
        pass

    def getPreviewsContent(self) -> List[Tuple[bytes, str]]:
        pass


class ModSource(BaseModClass):
    regexSpriteFile = re.compile(r"DefineSprite_(\d+)_?(.+|)?")
    regexSoundFile = re.compile(r"\d+_([^.]+)")
    regexAsFile = re.compile(r"([^.]+)\.as")

    def __init__(self, modSourcesPath: str):
        SendNotification(NotificationType.LoadingModSource, modSourcesPath)

        self.modSourcesPath = modSourcesPath
        self.folderName = os.path.basename(modSourcesPath)
        self.cachePath = os.path.join(self.modSourcesPath, MODS_SOURCES_CACHE_FILE)
        self.previewsPath = os.path.join(self.modSourcesPath, MODS_SOURCES_CACHE_PREVIEW)
        if MODS_PATH:
            self.modPath = os.path.join(MODS_PATH[0], f"{self.folderName}.{MOD_FILE_FORMAT}")
        else:
            self.modPath = os.path.join(MODS_SOURCES_PATH[0], f"{self.folderName}.{MOD_FILE_FORMAT}")

        self.loadModData()

    def loadModData(self):
        loaded = self.loadJsonFile(self.cachePath, ignoredVars=["formatVersion", "swfs", "files", "previewsIds"])

        if not loaded:
            #print(f"New mod source '{self.folderName}' detected")
            self.saveModData()

    def saveModData(self):
        if not hasattr(self, "hash") or not self.hash:
            self.hash = RandomHash()

        self.saveJsonFile(self.cachePath)

    def setGameVersion(self, gameVersion: str):
        self.gameVersion = gameVersion

    def setName(self, name: str):
        self.name = name

    def setAuthor(self, author: str):
        self.author = author

    def setVersion(self, version: str):
        self.version = version

    def setDescription(self, description: str):
        self.description = description

    def setTags(self, tags: list):
        self.tags = tags

    def setPreviewsPaths(self, previewsPaths: list):
        if not os.path.exists(self.previewsPath):
            os.mkdir(self.previewsPath)

        removePreviewPath = self.getPreviewsPaths()

        for n, previewPath in enumerate(previewsPaths):
            previewFormat = os.path.splitext(previewPath)[1]
            if previewPath and os.path.exists(previewPath):
                cachePreviewPath = os.path.join(self.previewsPath, f"preview{n}{previewFormat}")

                if cachePreviewPath in removePreviewPath:
                    removePreviewPath.remove(cachePreviewPath)

                with open(previewPath, "rb") as orig:
                    image = orig.read()
                with open(cachePreviewPath, "wb") as new:
                    new.write(image)
                del image

        for previewPath in removePreviewPath:
            os.remove(previewPath)

    def getPreviewsPaths(self) -> List[str]:
        previewsPaths = []
        if os.path.exists(self.previewsPath):
            for previewPath in os.listdir(self.previewsPath):
                previewsPaths.append(os.path.join(self.previewsPath, previewPath))

        return previewsPaths

    def getPreviewsContent(self) -> List[Tuple[bytes, str]]:
        previews = []

        if os.path.exists(self.previewsPath):
            for previewPath in self.getPreviewsPaths():
                previewFormat = os.path.splitext(previewPath)[1][1:]
                with open(previewPath, "rb") as preview:
                    previews.append((preview.read(), previewFormat))

        return previews

    def getElementsCount(self):
        return len([file for root, dirs, files in os.walk(self.modSourcesPath) for file in files]) - \
               len(self.getPreviewsPaths()) - 1  # 1 - _cache.json

    def compile(self):
        SendNotification(NotificationType.CompileElementsCount, self.hash, self.getElementsCount())

        if os.path.exists(self.modPath):
            os.remove(self.modPath)

        modSwf = Swf(self.modPath)
        self.swfs = {}
        self.previewsIds = {}
        self.files = {}

        for folder in os.listdir(self.modSourcesPath):
            folderPath = os.path.join(self.modSourcesPath, folder)

            if os.path.isfile(folderPath):
                continue

            # Import game elements
            if folder.endswith(".swf") and folder in BRAWLHALLA_SWFS:
                gameSwfName: str = folder
                elementsMap = {}
                self.swfs[gameSwfName] = {}
                self.swfs[gameSwfName]["scripts"] = {}
                self.swfs[gameSwfName]["sounds"] = []
                self.swfs[gameSwfName]["sprites"] = []

                for category in os.listdir(folderPath):
                    categoryPath = os.path.join(folderPath, category)

                    for elementPath in os.listdir(categoryPath):
                        if category == "scripts":
                            if script := self.regexAsFile.findall(elementPath):
                                scriptAnchor = script[0]
                                #print("Import ActionScript", scriptAnchor)
                                SendNotification(NotificationType.CompileModSourcesImportActionScripts,
                                                 self.hash, scriptAnchor)

                                with open(os.path.join(categoryPath, elementPath), "r") as actionScript:
                                    self.swfs[gameSwfName]["scripts"][scriptAnchor] = actionScript.read()

                        elif category == "sounds":
                            if sound := self.regexSoundFile.findall(elementPath):
                                soundAnchor = sound[0]
                                #print("Import Sound", soundAnchor)
                                SendNotification(NotificationType.CompileModSourcesImportSound, self.hash, soundAnchor)

                                self.swfs[gameSwfName]["sounds"].append(soundAnchor)

                                soundTag = modSwf.importSoundFile(os.path.join(categoryPath, elementPath))
                                modSwf.symbolClass.addTag(GetElementId(soundTag), soundAnchor)

                        elif category == "sprites":
                            if sprite := self.regexSpriteFile.findall(elementPath):
                                _, spriteAnchor = sprite[0]

                                SendNotification(NotificationType.CompileModSourcesImportSprite,
                                                 self.hash, spriteAnchor)

                                if not spriteAnchor:
                                    SendNotification(NotificationType.CompileModSourcesSpriteHasNoSymbolclass,
                                                     self.hash, elementPath)
                                    continue

                                self.swfs[gameSwfName]["sprites"].append(spriteAnchor)

                                spriteSwf = Swf(os.path.join(categoryPath, elementPath, "frames.swf"))

                                spriteElement = None
                                spriteId = 0
                                for element in spriteSwf.elementsList[::-1]:
                                    if isinstance(element, DefineSpriteTag):
                                        spriteElement = element
                                        spriteId = GetElementId(element)
                                        break
                                else:
                                    #print("Not found sprite in:", elementPath)
                                    SendNotification(NotificationType.CompileModSourcesSpriteNotFoundInFolder,
                                                     self.hash, elementPath)
                                    continue

                                cloneSprites = []
                                cloneShapes = []

                                for element in sorted(spriteSwf.elementsList, key=lambda x: GetElementId(x)):
                                    if not isinstance(element,
                                                      (CSMTextSettingsTag, DefineFontNameTag,
                                                       DefineFontAlignZonesTag, PlaceObject2Tag)):

                                        if GetElementId(element) in elementsMap:
                                            if element == spriteElement:
                                                for _element in spriteSwf.elementsList:
                                                    if isinstance(_element, (*DefineShapeTags, DefineEditTextTag,
                                                                             DefineSpriteTag,
                                                                             *DefineBitsLosslessTags)) or \
                                                            element == spriteElement:

                                                        elementsMap.pop(GetElementId(_element), None)
                                            else:
                                                continue

                                        newElId = modSwf.getNextCharacterId()
                                        cloneEl = modSwf.cloneAndAddElement(element, newElId)
                                        elementsMap[GetElementId(element)] = GetElementId(cloneEl)

                                        if isinstance(cloneEl, DefineShapeTags):
                                            if GetShapeBitmapId(cloneEl) is not None:
                                                cloneShapes.append(cloneEl)

                                        elif isinstance(cloneEl, DefineSpriteTag):
                                            cloneSprites.append(cloneEl)

                                        elif isinstance(element, DefineFontTags):
                                            for dependentElement in spriteSwf.getElementById(GetElementId(element),
                                                                                             (DefineFontNameTag,
                                                                                              DefineFontAlignZonesTag)):
                                                modSwf.cloneAndAddElement(dependentElement, newElId)

                                        elif isinstance(element, DefineEditTextTag):
                                            if dependentElement := spriteSwf.getElementById(GetElementId(element),
                                                                                            CSMTextSettingsTag):
                                                modSwf.cloneAndAddElement(dependentElement[0], newElId)
                                            cloneEl.fontId = elementsMap[element.fontId]

                                        elif isinstance(element, DefineTextTag):
                                            if dependentElement := spriteSwf.getElementById(GetElementId(element),
                                                                                            CSMTextSettingsTag):
                                                modSwf.cloneAndAddElement(dependentElement[0], newElId)

                                            for textRecord in cloneEl.textRecords:
                                                if textRecord.styleFlagsHasFont:
                                                    textRecord.fontId = elementsMap[textRecord.fontId]

                                for cloneSprite in cloneSprites:
                                    for sEl in cloneSprite.getTags().iterator():
                                        if isinstance(sEl, PlaceObject2Tag) and sEl.characterId > 0:
                                            SetElementId(sEl, elementsMap[sEl.characterId])
                                        elif isinstance(sEl, PlaceObject3Tag) and sEl.characterId > 0:
                                            SetElementId(sEl, elementsMap[sEl.characterId])

                                for cloneShape in cloneShapes:
                                    bitmapId = GetShapeBitmapId(cloneShape)
                                    SetShapeBitmapId(cloneShape, elementsMap[bitmapId])

                                if cloneSprites:
                                    modSwf.symbolClass.addTag(elementsMap[spriteId], spriteAnchor)
                                else:
                                    SendNotification(NotificationType.CompileModSourcesSpriteEmpty,
                                                     self.hash, spriteAnchor)

                        else:
                            #print(f"Error: Unsupported category '{category}'")
                            SendNotification(NotificationType.CompileModSourcesUnsupportedCategory, self.hash, category)

            # Import previews
            elif folder.startswith("_"):
                if folder == MODS_SOURCES_CACHE_PREVIEW:
                    for n, preview in enumerate(os.listdir(folderPath)):
                        #print("Import Preview", n)
                        SendNotification(NotificationType.CompileModSourcesImportPreview, self.hash, n)

                        binaryTag = modSwf.importBinaryFile(os.path.join(folderPath, preview))
                        previewFormat = os.path.splitext(preview)[1][1:]
                        self.previewsIds[GetElementId(binaryTag)] = previewFormat

            # Import images, music
            elif os.path.isdir(folderPath):
                for path, folders, files in os.walk(folderPath):
                    for file in files:
                        # Calculate relative path from mod source root
                        relative_path = os.path.relpath(os.path.join(path, file), self.modSourcesPath)
                        # Normalize path separators for cross-platform compatibility
                        relative_path = relative_path.replace("\\", "/")
                        
                        # Check if this file matches any Brawlhalla file (by relative path or filename)
                        file_key = None
                        if relative_path in BRAWLHALLA_FILES:
                            file_key = relative_path
                        else:
                            # Fallback: check by filename only (legacy support)
                            for brawlhalla_path in BRAWLHALLA_FILES.keys():
                                if os.path.basename(brawlhalla_path) == file:
                                    file_key = brawlhalla_path
                                    break
                        
                        if file_key:
                            #print("Import File", file_key)
                            SendNotification(NotificationType.CompileModSourcesImportFile, self.hash, file_key)

                            binaryTag = modSwf.importBinaryFile(os.path.join(path, file))
                            self.files[GetElementId(binaryTag)] = file_key

                        else:
                            #print("Error: Unknown file:", file)
                            SendNotification(NotificationType.CompileModSourcesUnknownFile, self.hash, file)

        try:
            modSwf.metaData.set(self.getDict())
            modSwf.save()
            modSwf.close()
            del modSwf
            SendNotification(NotificationType.CompileModSourcesFinished, self.hash)
        except:
            SendNotification(NotificationType.CompileModSourcesSaveError, self.hash)

    def delete(self):
        shutil.rmtree(self.modSourcesPath)


class ModsHashSumCache(DataClass):
    DataVariable(METADATA_FORMAT_CACHE_MODS_HASH_SUM, 0, "formatVersion")
    formatVersion: str = METADATA_FORMAT_VERSION

    DataVariable(METADATA_FORMAT_CACHE_MODS_HASH_SUM, 0, "formatType")
    formatType: str = METADATA_FORMAT_CACHE_MODS_HASH_SUM

    DataVariable(METADATA_FORMAT_CACHE_MODS_HASH_SUM, 1, "hashes")
    hashes: Dict[str, str]  # {hashSum: modHash}

    def __init__(self, modsHashSumCachePath: str):
        self.path = os.path.join(modsHashSumCachePath, METADATA_CACHE_MODS_HASH_SUM_FILE)
        self.loadJsonFile(self.path)

    def save(self):
        self.saveJsonFile(self.path)

    def setHash(self, hashSum: str, modHash: str):
        self.hashes[hashSum] = modHash

    def getHash(self, hashSum) -> Union[str, None]:
        return self.hashes.get(hashSum, None)

    def getHashSum(self, modHash: str) -> Union[str, None]:
        for hashSum, _modHash in self.hashes.items():
            if modHash == _modHash:
                return hashSum

        return None

    def removeHash(self, hashSum: str):
        self.hashes.pop(hashSum)


class ModCache(BaseModClass):
    DataVariable(METADATA_FORMAT_CACHE_MOD, 0, "formatType")
    formatType: str = METADATA_FORMAT_CACHE_MOD

    DataVariable(METADATA_FORMAT_CACHE_MOD, 1, "hashSum")
    hashSum: str

    DataVariable(METADATA_FORMAT_CACHE_MOD, 1, "installed")
    installed: bool = False

    DataVariable(METADATA_FORMAT_CACHE_MOD, 1, "currentVersion")
    currentVersion: bool = True

    DataVariable(METADATA_FORMAT_CACHE_MOD, 1, "modFileExist")
    modFileExist: bool = True

    modCachePath: str

    def loadCache(self, allowedVars=None, ignoredVars=None):
        if self.modCachePath:
            self.loadJsonFile(os.path.join(self.modCachePath, METADATA_CACHE_MOD_FILE),
                              allowedVars=allowedVars,
                              ignoredVars=ignoredVars)

    def saveCache(self):
        if self.modCachePath:
            self.saveJsonFile(os.path.join(self.modCachePath, METADATA_CACHE_MOD_FILE))


class ModClass(ModCache):
    def __init__(self, modsCachePath: str, modPath: str = None, modHash: str = None):
        self.modPath = modPath
        self.modsHashSumCache = ModsHashSumCache(modsCachePath)
        self.as3files = {}  # Add default empty as3files dictionary

        SendNotification(NotificationType.LoadingMod, modPath)

        if self.modPath is not None and os.path.exists(self.modPath):
            self.modFileExist = True

            self.modSwf = Swf(self.modPath, autoload=False)
            modHashSum = HashFile(self.modPath)

            _cache = False

            if modHash := self.modsHashSumCache.getHash(modHashSum):
                self.modCachePath = os.path.join(modsCachePath, modHash)
                if os.path.exists(self.modCachePath):
                    self.loadCache(ignoredVars=["modFileExist"])
                else:
                    _cache = True
            else:
                _cache = True

            if _cache:
                SendNotification(NotificationType.LoadingModData, modPath)
                self.loadModData()

                self.hashSum = modHashSum
                self.modCachePath = os.path.join(modsCachePath, self.hash)

                if oldHashSum := self.modsHashSumCache.getHashSum(self.hash):
                    self.modsHashSumCache.removeHash(oldHashSum)
                else:
                    if not os.path.exists(self.modCachePath):
                        os.mkdir(self.modCachePath)

                self.cachePreviews()

                self.modsHashSumCache.setHash(modHashSum, self.hash)
                self.modsHashSumCache.save()

                self.loadCache(allowedVars=["installed"])
        elif modHash is not None:
            self.modFileExist = False
            self.modSwf = None
            self.modCachePath = os.path.join(modsCachePath, modHash)
            self.hash = modHash
            # if modHashSum := self.modsHashSumCache.getHashSum(modHash):
            #    self.modsHashSumCache.removeHash(modHashSum)
            #    self.modsHashSumCache.save()
            if os.path.exists(self.modCachePath):
                self.loadCache(ignoredVars=["modFileExist"])
            else:
                self.removeCache()
                raise Exception("Not found mods cache")
        else:
            SendNotification(NotificationType.LoadingModIsEmpty, None, modPath)

        if BRAWLHALLA_VERSION is not None and BRAWLHALLA_VERSION == self.gameVersion:
            self.currentVersion = True
        else:
            self.currentVersion = False

        if self.modPath is not None:
            self.saveCache()

    def open(self):
        self.modSwf.open()

    def close(self):
        self.modSwf.close()

    def removeCache(self):
        if modHashSum := self.modsHashSumCache.getHashSum(self.hash):
            self.modsHashSumCache.removeHash(modHashSum)
            self.modsHashSumCache.save()

        shutil.rmtree(self.modCachePath)

    def loadModData(self):
        modOpen = self.modSwf.isOpen()

        if not modOpen:
            self.open()

        self.loadFromJson(self.modSwf.metaData.get(), ignoredVars=["formatType", "hashSum", "installed",
                                                                   "currentVersion", "modFileExist"])

        if not modOpen:
            self.close()

    def cachePreviews(self):
        SendNotification(NotificationType.LoadingModCachePreviews, self.hash)

        modOpen = self.modSwf.isOpen()
        modCachePreviewsPath = os.path.join(self.modCachePath, METADATA_CACHE_MOD_PREVIEWS_FOLDER)

        if not os.path.exists(modCachePreviewsPath):
            os.mkdir(modCachePreviewsPath)

        if not modOpen:
            self.open()

        for file in os.listdir(modCachePreviewsPath):
            os.remove(os.path.join(modCachePreviewsPath, file))

        for n, (elId, previewFormat) in enumerate(self.previewsIds.items()):
            self.modSwf.exportBinaryFile(os.path.join(modCachePreviewsPath, f"preview{n}.{previewFormat}"),
                                         elId=elId)

        if not modOpen:
            self.close()

    def getPreviewsPaths(self) -> List[str]:
        previewsPaths = []

        modCachePreviewsPath = os.path.join(self.modCachePath, METADATA_CACHE_MOD_PREVIEWS_FOLDER)
        if os.path.exists(modCachePreviewsPath):
            for file in os.listdir(modCachePreviewsPath):
                previewsPaths.append(os.path.join(modCachePreviewsPath, file))

        return previewsPaths

    def getPreviewsContent(self) -> List[Tuple[bytes, str]]:
        previewsContent = []

        for previewPath in self.getPreviewsPaths():
            previewFormat = os.path.splitext(previewPath)[1][1:]

            with open(previewPath, "rb") as file:
                previewsContent.append((file.read(), previewFormat))

        return previewsContent

    def getElementsCount(self):
        return len(self.files) + len([j for i in self.swfs.values() for n in i.values() for j in n])

    def getModConflict(self) -> List[str]:
        LOCK.acquire(True)

        SendNotification(NotificationType.ModElementsCount, self.hash, len(self.swfs))

        temp_gameFiles = []
        conflictMods = set(GameFiles.getModConflict(list(self.files.values()), self.hash))
        for swfName, swfMap in self.swfs.items():
            gameFile = GetGameFileClass(swfName)
            gameFile.open()

            SendNotification(NotificationType.ModConflictSearchInSwf, self.hash, swfName)

            temp_gameFiles.append(gameFile)

            for category, anchors in swfMap.items():
                if category in ("sounds", "sprites", "scripts"):
                    conflictAnchors = set(list(anchors)) & set(list(gameFile.modifiedAnchorsMap))

                    for anchor in conflictAnchors:
                        if modHash := gameFile.modifiedAnchorsMap.get(anchor, None):
                            conflictMods.add(modHash)

                    del conflictAnchors

            gameFile.close()

        if conflictMods:
            pass
            # print("Mod conflict:", list(conflictMods))
            SendNotification(NotificationType.ModConflict, self.hash, list(conflictMods))
        else:
            del temp_gameFiles
            SendNotification(NotificationType.ModConflictNotFound, self.hash)
            #del conflictMods

        LOCK.release()

        return list(conflictMods)

    def install(self, forceInstallation=False):
        """Install a mod"""
        LOCK.acquire(True)
        
        # Create logs directory if needed
        log_dir = os.path.join(MODLOADER_CACHE_PATH, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        # Log that we're installing this mod
        with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
            log_file.write(f"\n\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Installing mod: {self.name} (Hash: {self.hash})\n")
            log_file.write(f"Files in mod: {list(self.files.items())}\n")

        SendNotification(NotificationType.ModElementsCount, self.hash, self.getElementsCount())

        self.open()
        
        # Check conflict mods
        if not forceInstallation:
            conflictMods = self.getModConflict()
            if conflictMods:
                SendNotification(NotificationType.ModConflict, self.hash, list(conflictMods))
                return conflictMods

        else:
            pass
            #SendNotification(NotificationType.ForceInstallation, self.hash)
        
        # Indicates if the mod contains any language.bin files
        has_language_bin = False
        has_bnk_files = False
        language_files_processed = []
        bnk_files_processed = []

        # Track language installation order
        language_install_order_path = os.path.join(MODLOADER_CACHE_PATH, "language_install_order.json")
        if os.path.exists(language_install_order_path):
            with open(language_install_order_path, "r") as f:
                language_install_order = json.load(f)
        else:
            language_install_order = []
        
        # Process files with progress tracking
        total_files = len(self.files)
        processed_files = 0
        
        for elId, fileName in self.files.items():
            # Update progress for file processing
            processed_files += 1
            SendNotification(NotificationType.InstallingModFile, self.hash, fileName)
            
            fileElement = self.modSwf.getElementById(elId)
            if fileElement:
                fileElement = fileElement[0]
            else:
                #print(f"Error: Not found element '{[elId]}', fileElement)
                SendNotification(NotificationType.InstallingModNotFoundFileElement, self.hash, elId)
                continue

            # Add progress update before heavy operation
            SendNotification(NotificationType.Debug, f"Processing file {processed_files}/{total_files}: {fileName}")
            file_data = self.modSwf.exportBinaryData(fileElement)
            
            # Log file info
            with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
                log_file.write(f"Processing file: {fileName}, Size: {len(file_data)} bytes\n")
            
            # Check if this is a language file (.bin or .txt)
            is_language_file = (fileName.startswith("language.") and fileName.endswith(".bin")) or fileName.endswith("_language.txt")
            
            if is_language_file:
                SendNotification(NotificationType.Debug, f"Found language file: {fileName} in mod {self.hash}")
                has_language_bin = True
                language_files_processed.append(fileName)
                
                # Handle language file with specialized handler
                from .langbin import lang_bin_handler
                
                # Create a debug message
                SendNotification(NotificationType.Debug, f"Calling language handler for: {fileName}")
                
                # Save file to a temporary location with a unique name to avoid conflicts
                import uuid
                temp_id = str(uuid.uuid4())[:8]
                temp_file_path = os.path.join(MODLOADER_CACHE_PATH, f"temp_{temp_id}_{fileName}")
                
                try:
                    # Write the file data to the temporary file
                    with open(temp_file_path, "wb") as tmp_file:
                        tmp_file.write(file_data)
                    
                    # Process the language file and apply its changes
                    try:
                        # Add original file name as a parameter to help match the correct game file
                        success = lang_bin_handler.apply_mod_language_changes(temp_file_path, self.hash, original_filename=fileName)
                        
                        if success:
                            SendNotification(NotificationType.Success, f"Successfully applied language changes from {fileName}")
                        else:
                            SendNotification(NotificationType.Error, f"Failed to apply language changes from {fileName}")
                    except Exception as e:
                        SendNotification(NotificationType.Error, f"Error processing language file: {str(e)}")
                except Exception as e:
                    SendNotification(NotificationType.Error, f"Error saving temporary language file: {str(e)}")
                
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except Exception as e:
                        with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
                            log_file.write(f"Error removing temporary file: {str(e)}\n")
            
            # Check if this is a .bnk file
            elif fileName.endswith(".bnk"):
                has_bnk_files = True
                bnk_files_processed.append(fileName)
                
                # Handle .bnk file with specialized handler
                SendNotification(NotificationType.Debug, f"Found .bnk file in mod: {fileName}")
                
                # Save file to a temporary location
                temp_file_path = os.path.join(MODLOADER_CACHE_PATH, f"temp_{fileName}")
                try:
                    # Write the binary data to the temporary file
                    with open(temp_file_path, "wb") as tmp_file:
                        tmp_file.write(file_data)
                    
                    # Process the .bnk file and apply its changes
                    success = bnk_handler.apply_mod_changes(temp_file_path, self.hash, fileName)
                    
                    if success:
                        SendNotification(NotificationType.Success, f"Successfully applied BNK changes from {fileName}")
                    else:
                        SendNotification(NotificationType.Error, f"Failed to apply BNK changes from {fileName}")
                        
                except Exception as e:
                    SendNotification(NotificationType.Error, f"Error processing BNK file: {str(e)}")
                    
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except Exception as e:
                        with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
                            log_file.write(f"Error removing temporary BNK file: {str(e)}\n")
            else:
                # Regular file installation
                GameFiles.installFile(fileName, file_data, self.hash)
        
        # Process SWF files with progress tracking
        total_swfs = len(self.swfs)
        processed_swfs = 0
        
        for swfName, swfMap in self.swfs.items():
            processed_swfs += 1
            SendNotification(NotificationType.Debug, f"Processing SWF {processed_swfs}/{total_swfs}: {swfName}")
            
            gameFile = GetGameFileClass(swfName)
            gameFile.open()

            if gameFile is None:
                #print(f"Error: Not found swf '{swfName}'!")
                SendNotification(NotificationType.InstallingModNotFoundGameSwf, self.hash, swfName)
                continue

            if self.hash in gameFile.installed:
                #print(f"Mod '{self.name}' in '{swfName}' is already installed")
                SendNotification(NotificationType.InstallingModInFileAlreadyInstalled, self.hash, swfName)
                continue
            else:
                #print(f"Installing '{self.name}' in '{swfName}'")
                SendNotification(NotificationType.InstallingModSwf, self.hash, swfName)

            # Count total elements for progress tracking
            total_elements = sum(len(elements) for elements in swfMap.values())
            processed_elements = 0
            
            for category, elements in swfMap.items():
                if category == "scripts":
                    for scriptAnchor, content in elements.items():
                        processed_elements += 1
                        SendNotification(NotificationType.InstallingModSwfScript, self.hash, scriptAnchor)
                        SendNotification(NotificationType.Debug, f"Processing script {processed_elements}/{total_elements}: {scriptAnchor}")

                        success = gameFile.importScript(content, scriptAnchor, self.hash)

                        if not success:
                            SendNotification(NotificationType.InstallingModSwfScriptError, self.hash, scriptAnchor)

                elif category == "sounds":
                    for soundAnchor in elements:
                        processed_elements += 1
                        #print("Install Sound", soundAnchor)
                        SendNotification(NotificationType.InstallingModSwfSound, self.hash, soundAnchor)
                        SendNotification(NotificationType.Debug, f"Processing sound {processed_elements}/{total_elements}: {soundAnchor}")

                        try:
                            soundId = self.modSwf.symbolClass.getTagByName(soundAnchor)
                        except AttributeError:
                            # Fallback if getTagByName doesn't work
                            soundId = None
                            for tag_id, name in self.modSwf.symbolClass.getTags().items():
                                if name == soundAnchor:
                                    soundId = tag_id
                                    break
                                    
                        if soundId is None:
                            #print(f"Error: Sound {soundAnchor} does not exist")
                            SendNotification(NotificationType.InstallingModSwfSoundSymbolclassNotExist,
                                            self.hash, soundAnchor, swfName)
                            continue

                        sound = self.modSwf.getElementById(soundId, DefineSoundTag)
                        if sound:
                            sound = sound[0]
                        else:
                            #print(f"Error: Sound {soundId} {soundAnchor} does not exist")
                            SendNotification(NotificationType.InstallingModSoundNotExist,
                                            self.hash, soundAnchor, soundId, swfName)
                            continue

                        gameFile.importSound(sound, soundAnchor, self.hash)

                elif category == "sprites":
                    for sprite in elements:
                        processed_elements += 1
                        # Check if sprite is a string or dictionary
                        sprite_name = sprite if isinstance(sprite, str) else sprite["name"]
                        SendNotification(NotificationType.Debug, f"Processing sprite {processed_elements}/{total_elements}: {sprite_name}")
                        
                        try:
                            spriteId = self.modSwf.symbolClass.getTagByName(sprite_name)
                        except AttributeError:
                            # Fallback if getTagByName doesn't work
                            spriteId = None
                            for tag_id, name in self.modSwf.symbolClass.getTags().items():
                                if name == sprite_name:
                                    spriteId = tag_id
                                    break
                                    
                        if spriteId is None:
                            #print(f"Error: sprite {sprite['name']} does not exist")
                            SendNotification(NotificationType.InstallingModSwfSpriteSymbolclassNotExist,
                                            self.hash, sprite_name, swfName)
                            continue

                        spriteTag = self.modSwf.getElementById(spriteId, DefineSpriteTag)
                        if spriteTag:
                            spriteTag = spriteTag[0]
                        else:
                            #print(f"Error: Sound {spriteId} {spriteTag['name']} does not exist")
                            SendNotification(NotificationType.InstallingModSpriteNotExist,
                                             self.hash, sprite_name, spriteId, swfName)
                            continue

                        gameFile.importSprite(spriteTag, sprite_name, self.hash)

            gameFile.addInstalledMod(self.hash)
            gameFile.save()
            gameFile.close()

        for fileName, asContent in self.as3files.items():
            SendNotification(NotificationType.InstallingModAs3File, self.hash, fileName)
        
        # Check for language.bin files modified by this mod
        # Log summary of language file handling
        with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
            log_file.write(f"Installation completed for mod: {self.name}\n")
            log_file.write(f"Language files processed: {language_files_processed}\n")
            log_file.write(f"Has language files: {has_language_bin}\n")

        self.installed = True
        self.saveCache()
        
        # Send completion notification after setting installed status
        SendNotification(NotificationType.InstallingModFinished, self.hash)

        LOCK.release()

    def uninstall(self):
        LOCK.acquire(True)

        SendNotification(NotificationType.ModElementsCount, self.hash, self.getElementsCount())

        # Create log directory if it doesn't exist
        log_dir = os.path.join(MODLOADER_CACHE_PATH, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Log uninstallation start
        with open(os.path.join(log_dir, "mod_uninstallation.txt"), "a", encoding="utf-8") as log_file:
            log_file.write(f"\n\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Uninstalling mod: {self.name} (Hash: {self.hash})\n")

        # Count how many mods are currently installed
        remaining_mods = 0
        mods_cache_path = os.path.join(MODLOADER_CACHE_PATH, "Mods")
        if os.path.exists(mods_cache_path):
            for mod_hash_dir in os.listdir(mods_cache_path):
                if mod_hash_dir == self.hash:
                    continue
                mod_cache_file = os.path.join(mods_cache_path, mod_hash_dir, "mod.json")
                if os.path.exists(mod_cache_file):
                    try:
                        with open(mod_cache_file, "r") as f:
                            mod_data = json.load(f)
                            if mod_data.get("installed"):
                                remaining_mods += 1
                    except json.JSONDecodeError:
                        continue
        
        with open(os.path.join(log_dir, "mod_uninstallation.txt"), "a", encoding="utf-8") as log_file:
            log_file.write(f"Remaining mods after uninstallation: {remaining_mods}\n")

        # Check for language.bin files modified by this mod
        has_language_bin = False
        has_bnk_files = False
        for elId, fileName in self.files.items():
            if fileName.startswith("language.") and fileName.endswith(".bin"):
                has_language_bin = True
            elif fileName.endswith(".bnk"):
                has_bnk_files = True
            if has_language_bin and has_bnk_files:
                break

        # Regular file uninstallation
        GameFiles.uninstallMod(self.hash)

        # Handle language.bin files uninstallation
        if has_language_bin:
            from .langbin import lang_bin_handler
            # Use the tracked changes to revert only this mod's changes
            lang_bin_handler.uninstall_mod_language_changes(self.hash)
            
            # If this is the last mod, restore all original language files
            if remaining_mods == 0:
                with open(os.path.join(log_dir, "mod_uninstallation.txt"), "a", encoding="utf-8") as log_file:
                    log_file.write("No mods remaining, forcing restore of all original language files\n")
                lang_bin_handler.restore_all_original_files()
                
        # Handle .bnk files uninstallation
        if has_bnk_files:
            # Use the tracked changes to revert only this mod's changes
            bnk_handler.uninstall_mod_changes(self.hash)
            
            # If this is the last mod, restore all original .bnk files
            if remaining_mods == 0:
                with open(os.path.join(log_dir, "mod_uninstallation.txt"), "a", encoding="utf-8") as log_file:
                    log_file.write("No mods remaining, forcing restore of all original BNK files\n")
                bnk_handler.restore_all_original_files()

        for swfName in self.swfs:
            gameFile = GetGameFileClass(swfName)
            gameFile.open()

            gameFile.uninstallMod(self.hash)

            gameFile.save()
            gameFile.close()

        SendNotification(NotificationType.UninstallingModFinished, self.hash)

        self.installed = False
        self.saveCache()

        LOCK.release()

    def reinstall(self):
        self.uninstall()
        self.install()

    def decompile(self):
        SendNotification(NotificationType.DecompilingMod, self.hash)

        # Create ModSource
        mod_source_path = os.path.join(MODS_SOURCES_PATH[0], self.name)
        if os.path.exists(mod_source_path):
            shutil.rmtree(mod_source_path)
        os.mkdir(mod_source_path)

        mod_source = ModSource(mod_source_path)
        mod_source.gameVersion = self.gameVersion
        mod_source.name = self.name
        mod_source.author = self.author
        mod_source.version = self.version
        mod_source.description = self.description
        mod_source.tags = self.tags
        mod_source.saveModData()

        # Extract Previews
        preview_paths = self.getPreviewsPaths()
        mod_source.setPreviewsPaths(preview_paths)

        self.open()

        # Extract Files
        files_path = os.path.join(mod_source_path, "files")
        if not os.path.exists(files_path):
            os.mkdir(files_path)
        for elId, file_name in self.files.items():
            file_element = self.modSwf.getElementById(elId)
            if file_element:
                file_element = file_element[0]
            else:
                SendNotification(NotificationType.DecompilingModNotFoundFileElement, self.hash, elId)
                continue

            file_data = self.modSwf.exportBinaryData(file_element)
            with open(os.path.join(files_path, file_name), "wb") as f:
                f.write(file_data)


        # Extract SWF data
        for swf_name, swf_map in self.swfs.items():
            swf_path = os.path.join(mod_source_path, swf_name)
            if not os.path.exists(swf_path):
                os.mkdir(swf_path)

            for category, elements in swf_map.items():
                category_path = os.path.join(swf_path, category)
                if not os.path.exists(category_path):
                    os.mkdir(category_path)

                if category == "scripts":
                    for script_anchor, content in elements.items():
                        with open(os.path.join(category_path, f"{script_anchor}.as"), "w") as f:
                            f.write(content)
                elif category == "sounds":
                    for sound_anchor in elements:
                        sound_id = self.modSwf.symbolClass.getTagByName(sound_anchor)
                        if sound_id is None:
                            continue
                        sound = self.modSwf.getElementById(sound_id, DefineSoundTag)
                        if sound:
                            sound = sound[0]
                        else:
                            continue
                        
                        sound_data = self.modSwf.exportBinaryData(sound)
                        with open(os.path.join(category_path, f"{sound_id}_{sound_anchor}.wav"), "wb") as f:
                            f.write(sound_data)

        self.close()
        SendNotification(NotificationType.DecompilingModFinished, self.hash)

    def delete(self):
        self.removeCache()
        if self.modPath:
            os.remove(self.modPath)

    def getTagNameSafe(self, tag_id):
        """Safely get tag name even if the method doesn't exist"""
        try:
            return self.modSwf.symbolClass.getTagName(tag_id)
        except AttributeError:
            # Fallback if getTagName doesn't exist
            for id, name in self.modSwf.symbolClass.getTags().items():
                if id == tag_id:
                    return name
            return None
