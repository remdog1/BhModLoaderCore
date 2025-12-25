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

    DataVariable([METADATA_FORMAT_MOD, METADATA_FORMAT_CACHE_MOD], 1, "features")
    features: List[str]

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

        # Initialize required attributes with default values
        if not hasattr(self, 'gameVersion'):
            self.gameVersion = ""
        if not hasattr(self, 'name'):
            self.name = ""
        if not hasattr(self, 'author'):
            self.author = ""
        if not hasattr(self, 'version'):
            self.version = ""
        if not hasattr(self, 'description'):
            self.description = ""
        if not hasattr(self, 'tags'):
            self.tags = []
        if not hasattr(self, 'previewsIds'):
            self.previewsIds = {}
        if not hasattr(self, 'swfs'):
            self.swfs = {}
        if not hasattr(self, 'files'):
            self.files = {}

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

            # Check for full .swf files in the root of the mod folder
            if os.path.isfile(folderPath) and folder.endswith(".swf"):
                # This is a full SWF file to be packaged and installed as-is
                if folder in BRAWLHALLA_SWFS:
                    SendNotification(NotificationType.CompileModSourcesImportFile, self.hash, folder)
                    print(f"Found full .swf file in root: {folder}")
                    binaryTag = modSwf.importBinaryFile(folderPath)
                    self.files[GetElementId(binaryTag)] = folder
                else:
                    SendNotification(NotificationType.CompileModSourcesUnknownFile, self.hash, 
                                    f"Unknown SWF file: {folder}. Only game SWF files can be replaced.")
                continue

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

            # Import images and music with folder path logic
            elif os.path.isdir(folderPath):
                for path, folders, files in os.walk(folderPath):
                    for file in files:
                        # Calculate relative path from mod source root (like SWF files)
                        relative_path = os.path.relpath(os.path.join(path, file), self.modSourcesPath)
                        relative_path = relative_path.replace("\\", "/")
                        
                        if file in BRAWLHALLA_FILES:
                            # Special handling for language files - always use just filename, never folder path
                            if file.startswith("language.") and file.endswith(".bin"):
                                SendNotification(NotificationType.CompileModSourcesImportFile, self.hash, file)
                                binaryTag = modSwf.importBinaryFile(os.path.join(path, file))
                                self.files[GetElementId(binaryTag)] = file  # Just filename: language.1.bin
                            # For images, try to find the best match considering folder structure
                            elif file.endswith(".png") or file.endswith(".jpg"):
                                # Get the folder name from the bmod path
                                bmod_folder = os.path.basename(path)
                                
                                # Try to find a game file that matches both filename and folder context
                                best_match = None
                                for game_file, game_path in BRAWLHALLA_FILES.items():
                                    if game_file == file:
                                        # Check if the game path contains the same folder name
                                        if bmod_folder.lower() in game_path.lower():
                                            best_match = game_file
                                            break
                                        elif best_match is None:
                                            # Fallback to first match if no folder match found
                                            best_match = game_file
                                
                                if best_match:
                                    print(f"✅ Installing image: {file} from folder {bmod_folder} -> {BRAWLHALLA_FILES[best_match]}")
                                    SendNotification(NotificationType.CompileModSourcesImportFile, self.hash, best_match)
                                    
                                    binaryTag = modSwf.importBinaryFile(os.path.join(path, file))
                                    # Store the relative path instead of just filename for images
                                    self.files[GetElementId(binaryTag)] = relative_path
                                else:
                                    print(f"❌ No suitable match for image: {file}")
                                    SendNotification(NotificationType.CompileModSourcesUnknownFile, self.hash, file)
                            # Special handling for WEM files - preserve folder structure for BNK matching
                            elif file.endswith(".wem"):
                                # Get the folder name from the bmod path
                                bmod_folder = os.path.basename(path)
                                
                                # Try to find a BNK file that matches the folder context
                                best_bnk_match = None
                                for game_file, game_path in BRAWLHALLA_FILES.items():
                                    if game_file.endswith(".bnk"):
                                        # Check if the game path contains the same folder name
                                        if bmod_folder.lower() in game_path.lower():
                                            best_bnk_match = game_file
                                            break
                                        elif best_bnk_match is None:
                                            # Fallback to first BNK match if no folder match found
                                            best_bnk_match = game_file
                                
                                if best_bnk_match:
                                    print(f"✅ Installing WEM: {file} from folder {bmod_folder} -> {BRAWLHALLA_FILES[best_bnk_match]}")
                                    SendNotification(NotificationType.CompileModSourcesImportFile, self.hash, best_bnk_match)
                                    
                                    binaryTag = modSwf.importBinaryFile(os.path.join(path, file))
                                    # Store the relative path to preserve folder context for BNK processing
                                    self.files[GetElementId(binaryTag)] = relative_path
                                else:
                                    print(f"❌ No suitable BNK match for WEM: {file}")
                                    SendNotification(NotificationType.CompileModSourcesUnknownFile, self.hash, file)
                            else:
                                # For other files (BNK, etc.), use original logic
                                #print("Import File", file)
                                SendNotification(NotificationType.CompileModSourcesImportFile, self.hash, file)

                                binaryTag = modSwf.importBinaryFile(os.path.join(path, file))
                                self.files[GetElementId(binaryTag)] = file

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
        print(f"🔧 ModClass constructor called with: modPath={modPath}, modHash={modHash}")
        self.modPath = modPath
        self.modsHashSumCache = ModsHashSumCache(modsCachePath)
        self.as3files = {}  # Add default empty as3files dictionary

        SendNotification(NotificationType.LoadingMod, modPath)

        if self.modPath is not None and os.path.exists(self.modPath):
            print(f"🔧 Mod file exists: {self.modPath}")
            self.modFileExist = True

            self.modSwf = Swf(self.modPath, autoload=False)
            modHashSum = HashFile(self.modPath)
            print(f"🔧 Mod hash: {modHashSum}")

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

        # Safely remove cache directory if it exists
        if os.path.exists(self.modCachePath):
            try:
                shutil.rmtree(self.modCachePath)
            except (OSError, FileNotFoundError) as e:
                # Cache directory might already be gone, that's okay
                print(f"Warning: Could not remove cache directory {self.modCachePath}: {e}")

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
            try:
                gameFile.open()
            except Exception as e:
                # Handle corrupted SWF file errors
                error_str = str(e)
                if "SwfOpenException" in error_str or "SWF header is too short" in error_str or "corrupted" in error_str.lower() or "Invalid SWF file" in error_str:
                    SendNotification(NotificationType.Error, f"Failed to check mod conflicts: {error_str}")
                    # Continue with other files, but log this error
                    with open(os.path.join(MODLOADER_CACHE_PATH, "logs", "mod_conflict_errors.log"), "a", encoding="utf-8") as log_file:
                        log_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error opening {swfName} for conflict check: {error_str}\n")
                    continue
                else:
                    # Re-raise other exceptions
                    raise

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
        print(f"🚀 INSTALL METHOD CALLED for mod: {self.hash}")
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
        has_wem_files = False
        language_files_processed = []
        bnk_files_processed = []
        wem_files_processed = []

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
        
        print(f"🔧 INSTALLING MOD: {self.hash}")
        print(f"📁 Total files to process: {total_files}")
        print(f"📁 Files in mod: {list(self.files.values())}")
        print(f"📁 Files in mod (detailed): {self.files}")
        
        for elId, fileName in self.files.items():
            # Update progress for file processing
            processed_files += 1
            SendNotification(NotificationType.InstallingModFile, self.hash, fileName)
            
            # Add comprehensive debug logging
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Processing file {processed_files}/{total_files}: {fileName}")
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: File ID: {elId}, File Name: {fileName}")
            
            fileElement = self.modSwf.getElementById(elId)
            if fileElement:
                fileElement = fileElement[0]
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: Found file element for {fileName}")
            else:
                SendNotification(NotificationType.Debug, f"❌ INSTALL: ERROR - Not found element '{elId}' for file '{fileName}'")
                SendNotification(NotificationType.InstallingModNotFoundFileElement, self.hash, elId)
                continue

            # Add progress update before heavy operation
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Exporting binary data for {fileName}")
            file_data = self.modSwf.exportBinaryData(fileElement)
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Exported {len(file_data)} bytes for {fileName}")
            
            # Log file info
            with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
                log_file.write(f"Processing file: {fileName}, Size: {len(file_data)} bytes\n")
            
            # Check if this is a language file (.bin or .txt)
            # Handle both direct files (language.1.bin) and files in folders (languages/language.1.bin)
            is_language_file = (
                ("language." in fileName and fileName.endswith(".bin")) or 
                fileName.endswith("_language.txt")
            )
            
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Processing file: {fileName}")
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Is language file: {is_language_file}")
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: File starts with 'language.': {fileName.startswith('language.')}")
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: File ends with '.bin': {fileName.endswith('.bin')}")
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: File ends with '_language.txt': {fileName.endswith('_language.txt')}")
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Contains 'language.': {'language.' in fileName}")
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Detection logic result: {('language.' in fileName and fileName.endswith('.bin')) or fileName.endswith('_language.txt')}")
            
            if is_language_file:
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: *** LANGUAGE FILE DETECTED ***")
                SendNotification(NotificationType.Debug, f"Found language file: {fileName} in mod {self.hash}")
                has_language_bin = True
                language_files_processed.append(fileName)
                
                # Handle language file with specialized handler
                from .langbin import lang_bin_handler
                
                # Create a debug message
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: Calling language handler for: {fileName}")
                
                # Save file to a temporary location with a unique name to avoid conflicts
                import uuid
                temp_id = str(uuid.uuid4())[:8]
                # Extract just the filename from the path to avoid directory issues
                filename_only = os.path.basename(fileName)
                temp_file_path = os.path.join(MODLOADER_CACHE_PATH, f"temp_{temp_id}_{filename_only}")
                
                try:
                    # Write the file data to the temporary file
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Writing language file to temp: {temp_file_path}")
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Original filename: {fileName}, Extracted filename: {filename_only}")
                    with open(temp_file_path, "wb") as tmp_file:
                        tmp_file.write(file_data)
                    
                    # Process the language file and apply its changes
                    try:
                        # Add original file name as a parameter to help match the correct game file
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Calling apply_mod_language_changes with file: {fileName}")
                        success = lang_bin_handler.apply_mod_language_changes(temp_file_path, self.hash, original_filename=filename_only)
                        
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Language handler result: {success}")
                        if success:
                            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Language.txt result: True")
                            SendNotification(NotificationType.Success, f"Successfully applied language changes from {fileName}")
                        else:
                            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Language.txt result: False")
                            SendNotification(NotificationType.Error, f"Failed to apply language changes from {fileName}")
                    except Exception as e:
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Language.txt error: {str(e)}")
                        SendNotification(NotificationType.Error, f"Error processing language file: {str(e)}")
                except Exception as e:
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Error saving temp language file: {str(e)}")
                    SendNotification(NotificationType.Error, f"Error saving temporary language file: {str(e)}")
                
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Cleaned up temp language file: {temp_file_path}")
                    except Exception as e:
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Error removing temp language file: {str(e)}")
                        with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
                            log_file.write(f"Error removing temporary file: {str(e)}\n")
            
            # Check if this is a .bnk file
            elif fileName.endswith(".bnk"):
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: *** BNK FILE DETECTED ***")
                has_bnk_files = True
                bnk_files_processed.append(fileName)
                
                # Handle .bnk file with specialized handler
                SendNotification(NotificationType.Debug, f"Found .bnk file in mod: {fileName}")
                
                # Save file to a temporary location
                # Extract just the filename from the path to avoid directory issues
                filename_only = os.path.basename(fileName)
                temp_file_path = os.path.join(MODLOADER_CACHE_PATH, f"temp_{filename_only}")
                try:
                    # Write the binary data to the temporary file
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Writing BNK file to temp: {temp_file_path}")
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Original filename: {fileName}, Extracted filename: {filename_only}")
                    with open(temp_file_path, "wb") as tmp_file:
                        tmp_file.write(file_data)
                    
                    # Process the .bnk file and apply its changes
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Calling BNK handler for: {fileName}")
                    success = bnk_handler.apply_mod_changes(temp_file_path, self.hash, filename_only)
                    
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: BNK handler result: {success}")
                    if success:
                        SendNotification(NotificationType.Success, f"Successfully applied BNK changes from {fileName}")
                    else:
                        SendNotification(NotificationType.Error, f"Failed to apply BNK changes from {fileName}")
                        
                except Exception as e:
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: BNK processing error: {str(e)}")
                    SendNotification(NotificationType.Error, f"Error processing BNK file: {str(e)}")
                    
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Cleaned up temp BNK file: {temp_file_path}")
                    except Exception as e:
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Error removing temp BNK file: {str(e)}")
                        with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
                            log_file.write(f"Error removing temporary BNK file: {str(e)}\n")
            
            # Check if this is a .wem file
            elif fileName.endswith(".wem"):
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: *** WEM FILE DETECTED ***")
                has_wem_files = True
                wem_files_processed.append(fileName)
                SendNotification(NotificationType.Debug, f"Found .wem file in mod: {fileName}")
                
                # Handle .wem file with specialized handler
                # Determine the target BNK file based on folder structure
                filename_only = os.path.basename(fileName)
                target_bnk_file = None
                
                # If the fileName contains folder structure (e.g., "sounds/001.wem"), 
                # try to find the matching BNK file
                if "/" in fileName:
                    folder_name = fileName.split("/")[0]
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: WEM file in folder: {folder_name}")
                    
                    # Look for BNK files that might match this folder
                    for game_file, game_path in BRAWLHALLA_FILES.items():
                        if game_file.endswith(".bnk") and folder_name.lower() in game_path.lower():
                            target_bnk_file = game_file
                            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Found matching BNK: {target_bnk_file}")
                            break
                
                # If no specific BNK found, use the filename as fallback
                if target_bnk_file is None:
                    target_bnk_file = filename_only
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Using filename as BNK target: {target_bnk_file}")
                
                # Save file to a temporary location
                temp_file_path = os.path.join(MODLOADER_CACHE_PATH, f"temp_{filename_only}")
                try:
                    # Write the binary data to the temporary file
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Writing WEM file to temp: {temp_file_path}")
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Original filename: {fileName}, Extracted filename: {filename_only}")
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Target BNK file: {target_bnk_file}")
                    with open(temp_file_path, "wb") as tmp_file:
                        tmp_file.write(file_data)
                    
                    # Process the .wem file and apply its changes
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: Calling WEM handler for: {fileName}")
                    success = bnk_handler.apply_wem_file(temp_file_path, self.hash, target_bnk_file)
                    
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: WEM handler result: {success}")
                    if success:
                        SendNotification(NotificationType.Success, f"Successfully applied WEM changes from {fileName} to {target_bnk_file}")
                    else:
                        SendNotification(NotificationType.Error, f"Failed to apply WEM changes from {fileName} to {target_bnk_file}")
                        
                except Exception as e:
                    SendNotification(NotificationType.Debug, f"🔧 INSTALL: WEM processing error: {str(e)}")
                    SendNotification(NotificationType.Error, f"Error processing WEM file: {str(e)}")
                    
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Cleaned up temp WEM file: {temp_file_path}")
                    except Exception as e:
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Error removing temp WEM file: {str(e)}")
                        with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
                            log_file.write(f"Error removing temporary WEM file: {str(e)}\n")
            # Check if this is a full .swf file replacement
            elif fileName.endswith(".swf") and fileName in BRAWLHALLA_SWFS:
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: *** FULL SWF FILE REPLACEMENT DETECTED ***")
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: Installing full SWF file: {fileName}")
                # Install the full SWF file directly using GameFiles
                GameFiles.installFile(fileName, file_data, self.hash)
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: Completed full SWF file installation: {fileName}")
            
            else:
                # Regular file installation (including images)
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: *** REGULAR FILE DETECTED ***")
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: Installing regular file: {fileName}")
                GameFiles.installFile(fileName, file_data, self.hash)
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: Completed regular file installation: {fileName}")
        
        # Process SWF files with progress tracking
        total_swfs = len(self.swfs)
        processed_swfs = 0
        
        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Starting SWF processing - {total_swfs} SWF files to process")
        
        for swfName, swfMap in self.swfs.items():
            processed_swfs += 1
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Processing SWF {processed_swfs}/{total_swfs}: {swfName}")
            
            gameFile = GetGameFileClass(swfName)
            if gameFile is None:
                SendNotification(NotificationType.Debug, f"❌ INSTALL: ERROR - Game file not found for SWF: {swfName}")
                SendNotification(NotificationType.InstallingModNotFoundGameSwf, self.hash, swfName)
                continue
            
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Opening game file: {swfName}")
            try:
                gameFile.open()
            except Exception as e:
                # Handle corrupted SWF file errors
                error_str = str(e)
                if "SwfOpenException" in error_str or "SWF header is too short" in error_str or "corrupted" in error_str.lower() or "Invalid SWF file" in error_str:
                    error_msg = (
                        f"Failed to install mod '{self.name}': SWF file '{swfName}' is corrupted.\n\n"
                        f"{error_str}\n\n"
                        "This usually happens when the game file was corrupted during a previous operation.\n\n"
                        "Possible solutions:\n"
                        "1. Verify game files through Steam/Epic Games to restore the original file\n"
                        "2. Uninstall all mods and reinstall them one at a time\n"
                        "3. Restore the file from a backup if available\n"
                        "4. Reinstall the game if the file is a core game file"
                    )
                    SendNotification(NotificationType.Error, error_msg)
                    raise Exception(error_msg) from e
                else:
                    # Re-raise other exceptions
                    raise

            if self.hash in gameFile.installed:
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: Mod already installed in SWF: {swfName}")
                SendNotification(NotificationType.InstallingModInFileAlreadyInstalled, self.hash, swfName)
                continue
            else:
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: Installing mod in SWF: {swfName}")
                SendNotification(NotificationType.InstallingModSwf, self.hash, swfName)

            # Count total elements for progress tracking
            total_elements = sum(len(elements) for elements in swfMap.values())
            processed_elements = 0
            
            SendNotification(NotificationType.Debug, f"🔧 INSTALL: SWF {swfName} has {total_elements} elements to process")
            
            for category, elements in swfMap.items():
                SendNotification(NotificationType.Debug, f"🔧 INSTALL: Processing category '{category}' with {len(elements)} elements")
                
                if category == "scripts":
                    for scriptAnchor, content in elements.items():
                        processed_elements += 1
                        SendNotification(NotificationType.InstallingModSwfScript, self.hash, scriptAnchor)
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Processing script {processed_elements}/{total_elements}: {scriptAnchor}")

                        success = gameFile.importScript(content, scriptAnchor, self.hash)
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Script import result: {success}")

                        if not success:
                            SendNotification(NotificationType.Debug, f"❌ INSTALL: Script import failed: {scriptAnchor}")
                            SendNotification(NotificationType.InstallingModSwfScriptError, self.hash, scriptAnchor)

                elif category == "sounds":
                    for soundAnchor in elements:
                        processed_elements += 1
                        SendNotification(NotificationType.InstallingModSwfSound, self.hash, soundAnchor)
                        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Processing sound {processed_elements}/{total_elements}: {soundAnchor}")

                        try:
                            soundId = self.modSwf.symbolClass.getTagByName(soundAnchor)
                            SendNotification(NotificationType.Debug, f"🔧 INSTALL: Found sound ID: {soundId}")
                        except AttributeError:
                            SendNotification(NotificationType.Debug, f"❌ INSTALL: Sound not found in symbol class: {soundAnchor}")
                            continue
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

                        # Try to import with createIfNotExists=True for new sprites
                        # importSprite will handle detection and creation internally
                        success = gameFile.importSprite(spriteTag, sprite_name, self.hash, createIfNotExists=True)
                        if not success:
                            SendNotification(NotificationType.Debug, f"❌ INSTALL: Sprite import failed: {sprite_name}")
                            SendNotification(NotificationType.InstallingModSpriteNotExist,
                                             self.hash, sprite_name, spriteId, swfName)

            gameFile.addInstalledMod(self.hash)
            try:
                gameFile.save()
            except Exception as e:
                # Check if it's an OutOfMemoryError
                error_str = str(e)
                if "OutOfMemoryError" in error_str or "java.lang.OutOfMemoryError" in error_str:
                    gameFile.close()  # Make sure to close the file even on error
                    error_msg = (
                        f"Java ran out of memory while installing mod '{self.name}'.\n\n"
                        "This can happen with large mods or when processing multiple mods.\n\n"
                        "Possible solutions:\n"
                        "1. Close other applications to free up RAM\n"
                        "2. Install mods one at a time instead of multiple at once\n"
                        "3. Restart the mod loader to free up Java memory\n"
                        "4. If the problem persists, try deleting the bhloader cache folder and restarting"
                    )
                    SendNotification(NotificationType.Error, error_msg)
                    raise Exception(f"OutOfMemoryError installing mod '{self.name}': Java heap space exhausted. " + error_msg) from e
                else:
                    # Re-raise other exceptions as-is
                    raise
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
        # Final installation summary
        SendNotification(NotificationType.Debug, f"🎉 INSTALL: Installation completed for mod: {self.name}")
        SendNotification(NotificationType.Debug, f"🎉 INSTALL: Total files processed: {total_files}")
        SendNotification(NotificationType.Debug, f"🎉 INSTALL: Language files processed: {len(language_files_processed)}")
        SendNotification(NotificationType.Debug, f"🎉 INSTALL: BNK files processed: {len(bnk_files_processed)}")
        SendNotification(NotificationType.Debug, f"🎉 INSTALL: SWF files processed: {total_swfs}")
        
        if language_files_processed:
            SendNotification(NotificationType.Debug, f"🎉 INSTALL: Language files: {language_files_processed}")
        if bnk_files_processed:
            SendNotification(NotificationType.Debug, f"🎉 INSTALL: BNK files: {bnk_files_processed}")
        
        # Log final summary
        with open(os.path.join(log_dir, "mod_installation.txt"), "a", encoding="utf-8") as log_file:
            log_file.write(f"\n=== INSTALLATION SUMMARY ===\n")
            log_file.write(f"Mod: {self.name} (Hash: {self.hash})\n")
            log_file.write(f"Total files processed: {total_files}\n")
            log_file.write(f"Language files: {language_files_processed}\n")
            log_file.write(f"BNK files: {bnk_files_processed}\n")
            log_file.write(f"WEM files: {wem_files_processed}\n")
            log_file.write(f"SWF files: {total_swfs}\n")
            log_file.write(f"Installation completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"================================\n")

        # Send debug summary
        SendNotification(NotificationType.Debug, f"🔧 INSTALL: Installation Summary:")
        SendNotification(NotificationType.Debug, f"🔧 INSTALL: - Language files processed: {len(language_files_processed)}")
        SendNotification(NotificationType.Debug, f"🔧 INSTALL: - BNK files processed: {len(bnk_files_processed)}")
        SendNotification(NotificationType.Debug, f"🔧 INSTALL: - WEM files processed: {len(wem_files_processed)}")
        SendNotification(NotificationType.Debug, f"🔧 INSTALL: - SWF files processed: {total_swfs}")

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
        has_wem_files = False
        
        # Also check if mod_changes has entries for this mod (in case files aren't in self.files)
        # This handles cases where BNK/WEM files were installed but not properly tracked in self.files
        if hasattr(bnk_handler, 'mod_changes') and self.hash in bnk_handler.mod_changes:
            mod_bnk_changes = bnk_handler.mod_changes[self.hash]
            if mod_bnk_changes:
                has_bnk_files = True
                has_wem_files = True  # WEM changes are tracked in the same structure
                SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: Found BNK/WEM changes in mod_changes for mod: {self.hash}")
        
        # Check self.files for file-based detection
        for elId, fileName in self.files.items():
            # Use the same detection logic as in install process
            is_language_file = (
                ("language." in fileName and fileName.endswith(".bin")) or 
                fileName.endswith("_language.txt")
            )
            if is_language_file:
                has_language_bin = True
            elif fileName.endswith(".bnk") or (isinstance(fileName, str) and ".bnk" in fileName.lower()):
                has_bnk_files = True
            elif fileName.endswith(".wem") or (isinstance(fileName, str) and ".wem" in fileName.lower()):
                has_wem_files = True
            if has_language_bin and has_bnk_files and has_wem_files:
                break

        # Regular file uninstallation
        GameFiles.uninstallMod(self.hash)

        # Handle language.bin files uninstallation
        if has_language_bin:
            SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: *** LANGUAGE FILE UNINSTALL DETECTED ***")
            SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: Uninstalling language changes for mod: {self.hash}")
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
            SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: *** BNK FILE UNINSTALL DETECTED ***")
            SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: Uninstalling BNK changes for mod: {self.hash}")
            # Use the tracked changes to revert only this mod's changes
            try:
                uninstall_result = bnk_handler.uninstall_mod_changes(self.hash)
                if uninstall_result:
                    SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: BNK uninstall completed successfully")
                else:
                    SendNotification(NotificationType.Debug, f"⚠️ UNINSTALL: BNK uninstall returned False - changes may not have been found")
            except Exception as e:
                SendNotification(NotificationType.Error, f"Error uninstalling BNK changes: {str(e)}")
                with open(os.path.join(log_dir, "mod_uninstallation.txt"), "a", encoding="utf-8") as log_file:
                    log_file.write(f"Error uninstalling BNK changes: {str(e)}\n")
            
            # If this is the last mod, restore all original .bnk files
            if remaining_mods == 0:
                with open(os.path.join(log_dir, "mod_uninstallation.txt"), "a", encoding="utf-8") as log_file:
                    log_file.write("No mods remaining, forcing restore of all original BNK files\n")
                try:
                    bnk_handler.restore_all_original_files()
                except Exception as e:
                    SendNotification(NotificationType.Error, f"Error restoring original BNK files: {str(e)}")

        # Handle .wem files uninstallation
        # Note: WEM files use the same uninstall_mod_changes function as BNK files
        # since they're both tracked in the same mod_changes structure
        if has_wem_files and not has_bnk_files:  # Only call if BNK wasn't already handled
            SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: *** WEM FILE UNINSTALL DETECTED ***")
            SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: Uninstalling WEM changes for mod: {self.hash}")
            # Use the tracked changes to revert only this mod's changes
            try:
                uninstall_result = bnk_handler.uninstall_mod_changes(self.hash)
                if uninstall_result:
                    SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: WEM uninstall completed successfully")
                else:
                    SendNotification(NotificationType.Debug, f"⚠️ UNINSTALL: WEM uninstall returned False - changes may not have been found")
            except Exception as e:
                SendNotification(NotificationType.Error, f"Error uninstalling WEM changes: {str(e)}")
                with open(os.path.join(log_dir, "mod_uninstallation.txt"), "a", encoding="utf-8") as log_file:
                    log_file.write(f"Error uninstalling WEM changes: {str(e)}\n")

        for swfName in self.swfs:
            gameFile = GetGameFileClass(swfName)
            try:
                gameFile.open()
            except Exception as e:
                # Handle corrupted SWF file errors
                error_str = str(e)
                if "SwfOpenException" in error_str or "SWF header is too short" in error_str or "corrupted" in error_str.lower() or "Invalid SWF file" in error_str:
                    error_msg = (
                        f"Failed to uninstall mod '{self.name}': SWF file '{swfName}' is corrupted.\n\n"
                        f"{error_str}\n\n"
                        "This usually happens when the game file was corrupted during a previous operation.\n\n"
                        "Possible solutions:\n"
                        "1. Verify game files through Steam/Epic Games to restore the original file\n"
                        "2. Restore the file from a backup if available\n"
                        "3. Reinstall the game if the file is a core game file\n"
                        "Note: The mod will still be removed from the mod list, but the file may need manual restoration."
                    )
                    SendNotification(NotificationType.Error, error_msg)
                    # Continue with uninstall even if file is corrupted - at least remove from mod list
                    continue
                else:
                    # Re-raise other exceptions
                    raise

            gameFile.uninstallMod(self.hash)

            try:
                gameFile.save()
            except Exception as e:
                # Check if it's an OutOfMemoryError
                error_str = str(e)
                if "OutOfMemoryError" in error_str or "java.lang.OutOfMemoryError" in error_str:
                    gameFile.close()  # Make sure to close the file even on error
                    error_msg = (
                        f"Java ran out of memory while uninstalling mod '{self.name}'.\n\n"
                        "This can happen with large mods or when processing multiple mods.\n\n"
                        "Possible solutions:\n"
                        "1. Close other applications to free up RAM\n"
                        "2. Uninstall mods one at a time instead of multiple at once\n"
                        "3. Restart the mod loader to free up Java memory\n"
                        "4. If the problem persists, try deleting the bhloader cache folder and restarting"
                    )
                    SendNotification(NotificationType.Error, error_msg)
                    raise Exception(f"OutOfMemoryError uninstalling mod '{self.name}': Java heap space exhausted. " + error_msg) from e
                else:
                    # Re-raise other exceptions as-is
                    raise
            gameFile.close()

        # Send debug summary
        SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: Uninstall Summary:")
        SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: - Language files processed: {has_language_bin}")
        SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: - BNK files processed: {has_bnk_files}")
        SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: - WEM files processed: {has_wem_files}")
        SendNotification(NotificationType.Debug, f"🔧 UNINSTALL: - SWF files processed: {len(self.swfs)}")

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
        """Delete the mod file and cache. Handles cases where files may already be manually removed."""
        try:
            self.removeCache()
        except Exception as e:
            # Cache removal failed, but continue with file deletion
            print(f"Warning: Error removing cache during mod deletion: {e}")
        
        # Safely remove mod file if it exists
        if self.modPath:
            if os.path.exists(self.modPath):
                try:
                    os.remove(self.modPath)
                except (OSError, FileNotFoundError) as e:
                    # File might already be manually deleted, that's okay
                    print(f"Warning: Could not remove mod file {self.modPath}: {e}")
            else:
                # File doesn't exist (was manually removed), that's fine
                print(f"Info: Mod file {self.modPath} was already removed, cleaning up mod instance.")

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
