import os
from typing import Dict, List, Union

from .dataversion import DataVariable, DataClass
from .variables import METADATA_FORMAT_GAME, METADATA_FORMAT_VERSION
from .basedispatch import SendNotification

from .brawlhalla import BRAWLHALLA_SWFS
from ..swf.swf import (Swf,
                       GetNeededCharacters,
                       GetElementId,
                       SetElementId,
                       GetSwfByElement,
                       GetNeededCharactersId,
                       GetShapeBitmapId,
                       SetShapeBitmapId)
from ..ffdec.classes import (DefineSpriteTag,
                             DefineFontTags,
                             DefineFontNameTag,
                             DefineFontAlignZonesTag,
                             DefineEditTextTag,
                             DefineShapeTags,
                             DefineSoundTag,
                             CSMTextSettingsTag,
                             PlaceObject2Tag,
                             PlaceObject3Tag)
from ..notifications import NotificationType


class GameSwfData(DataClass):
    DataVariable(METADATA_FORMAT_GAME, 0, "formatVersion")
    formatVersion: int = METADATA_FORMAT_VERSION

    DataVariable(METADATA_FORMAT_GAME, 0, "formatType")
    formatType: str = METADATA_FORMAT_GAME

    DataVariable(METADATA_FORMAT_GAME, 1, "anchors")
    anchors: Dict[str, int]

    DataVariable(METADATA_FORMAT_GAME, 1, "scripts")
    scripts: Dict[str, str]

    DataVariable(METADATA_FORMAT_GAME, 1, "installed")
    installed: List[str]

    DataVariable(METADATA_FORMAT_GAME, 1, "modifiedAnchorsMap")
    modifiedAnchorsMap: Dict[str, str]


class GameSwf(GameSwfData):
    def __init__(self, gameFilePath: str):
        self.gameSwf = Swf(gameFilePath, autoload=False)

    def open(self):
        self.gameSwf.open()
        self.loadFileData()

    def save(self):
        self.gameSwf.metaData.set(self.getDict())
        self.gameSwf.save()

    def close(self):
        self.gameSwf.close()

    def loadFileData(self):
        fileOpen = self.gameSwf.isOpen()
        if not fileOpen:
            self.open()

        if self.gameSwf.metaData is None:
            self.gameSwf.addMetadata()
        else:
            self.loadFromJson(self.gameSwf.metaData.get())

        if not fileOpen:
            self.close()

    def saveFileData(self):
        self.saveJsonFile()

    def addInstalledMod(self, modHash: str):
        if modHash not in self.installed:
            self.installed.append(modHash)

    def importSound(self, sound: DefineSoundTag, soundAnchor: str, modHash: str):
        fileOpen = self.gameSwf.isOpen()
        if not fileOpen:
            self.open()

        origSoundId = self.gameSwf.symbolClass.getTagByName(soundAnchor)
        if origSoundId is None:
            print(f"Error: Element '{soundAnchor}' not found!")
            return
        origSound = self.gameSwf.getElementById(origSoundId, DefineSoundTag)[0]

        newOrigSoundId = self.gameSwf.getNextCharacterId()
        if self.gameSwf.symbolClass.getTag(newOrigSoundId) is not None:
            self.gameSwf.symbolClass.removeTag(newOrigSoundId)

        cloneSound = sound.cloneTag()
        self.gameSwf.cloneAndAddElement(origSound, newOrigSoundId)
        self.gameSwf.replaceElement(origSound, cloneSound)
        SetElementId(cloneSound, origSoundId)

        self.anchors[soundAnchor] = newOrigSoundId
        self.modifiedAnchorsMap[soundAnchor] = modHash

        if not fileOpen:
            self.close()

    def importSprite(self, sprite: DefineSpriteTag, spriteAnchor: str, modHash: str, elementsMap=None):
        fileOpen = self.gameSwf.isOpen()
        if elementsMap is None:
            elementsMap = {}
        cloneSprites = []
        cloneShapes = []

        if not fileOpen:
            self.open()

        origSpriteId = self.gameSwf.symbolClass.getTagByName(spriteAnchor)
        if origSpriteId is None:
            print(f"Error: Element '{spriteAnchor}' not found!")
            return
        origSprite = self.gameSwf.getElementById(origSpriteId, DefineSpriteTag)[0]

        for needElement in [*GetNeededCharacters(sprite), sprite]:
            if GetElementId(needElement) not in elementsMap:
                if needElement == sprite:
                    newElId = origSpriteId
                    cloneEl = sprite.cloneTag()
                    newOrigSpriteId = self.gameSwf.getNextCharacterId()
                    if self.gameSwf.symbolClass.getTag(newOrigSpriteId) is not None:
                        self.gameSwf.symbolClass.removeTag(newOrigSpriteId)
                    self.gameSwf.cloneAndAddElement(origSprite, newOrigSpriteId)
                    self.gameSwf.replaceElement(origSprite, cloneEl)
                    SetElementId(cloneEl, origSpriteId)

                    self.anchors[spriteAnchor] = newOrigSpriteId
                else:
                    newElId = self.gameSwf.getNextCharacterId()
                    cloneEl = self.gameSwf.cloneAndAddElement(needElement, newElId)

                    if self.gameSwf.symbolClass.getTag(newElId) is not None:
                        self.gameSwf.symbolClass.removeTag(newElId)

                elementsMap[GetElementId(needElement)] = newElId
                if isinstance(cloneEl, DefineShapeTags):
                    if GetShapeBitmapId(cloneEl) is not None:
                        cloneShapes.append(cloneEl)

                elif isinstance(cloneEl, DefineSpriteTag):
                    cloneSprites.append(cloneEl)

                if isinstance(needElement, DefineFontTags):
                    for dependentElement in GetSwfByElement(sprite).getElementById(GetElementId(needElement),
                                                                                   (DefineFontNameTag,
                                                                                   DefineFontAlignZonesTag)):
                        self.gameSwf.cloneAndAddElement(dependentElement, newElId)

                elif isinstance(needElement, DefineEditTextTag):
                    if dependentElement := GetSwfByElement(sprite).getElementById(GetElementId(needElement),
                                                                                  CSMTextSettingsTag):
                        self.gameSwf.cloneAndAddElement(dependentElement[0], newElId)
                    cloneEl.fontId = elementsMap[needElement.fontId]

        for cloneSprite in cloneSprites:
            for sEl in cloneSprite.getTags().iterator():
                if isinstance(sEl, PlaceObject2Tag) and sEl.characterId > 0:
                    SetElementId(sEl, elementsMap[sEl.characterId])
                elif isinstance(sEl, PlaceObject3Tag) and sEl.characterId > 0:
                    SetElementId(sEl, elementsMap[sEl.characterId])

        for cloneShape in cloneShapes:
            bitmapId = GetShapeBitmapId(cloneShape)
            SetShapeBitmapId(cloneShape, elementsMap[bitmapId])

        self.modifiedAnchorsMap[spriteAnchor] = modHash

        if not fileOpen:
            self.close()

    def uninstallMod(self, modHash: str):
        SendNotification(NotificationType.UninstallingModSwf, modHash, os.path.split(self.gameSwf.swfPath)[1])

        fileOpen = self.gameSwf.isOpen()
        if not fileOpen:
            self.open()

        # TODO: Scripts

        for anchor, _modHash in self.modifiedAnchorsMap.copy().items():
            if _modHash == modHash:
                origElId = self.anchors.get(anchor)
                if origElId is None:
                    #print(f"Error: Orig element '{anchor}' not found!")
                    SendNotification(NotificationType.UninstallingModSwfOriginalElementNotFound, _modHash, anchor)
                    continue
                origEl = self.gameSwf.getElementById(origElId)

                if origEl:
                    origEl = origEl[0]
                else:
                    print("Error: ")

                modElId = self.gameSwf.symbolClass.getTagByName(anchor)
                if modElId is None:
                    #print(f"Error: Mod element '{modElId}' not found!")
                    SendNotification(NotificationType.UninstallingModSwfElementNotFound, _modHash, anchor)
                    continue
                modEl = self.gameSwf.getElementById(modElId)

                if modEl:
                    modEl = modEl[0]
                else:
                    print("Error: ")

                if isinstance(modEl, DefineSoundTag):
                    #print(f"Remove Sound {anchor}")
                    SendNotification(NotificationType.UninstallingModSwfSound, _modHash, anchor)

                    self.gameSwf.removeElement(origEl)
                    self.gameSwf.replaceElement(modEl, origEl)
                    self.gameSwf.removeElement(modEl)
                    SetElementId(origEl, modElId)

                    self.gameSwf.symbolClass.setTag(modElId, anchor)

                    self.anchors.pop(anchor, None)
                    self.modifiedAnchorsMap.pop(anchor, None)

                elif isinstance(modEl, DefineSpriteTag):
                    #print(f"Remove Sprite {anchor}")
                    SendNotification(NotificationType.UninstallingModSwfSprite, _modHash, anchor)

                    for needElId in GetNeededCharactersId(modEl):
                        for needEl in self.gameSwf.getElementById(needElId):
                            self.gameSwf.removeElement(needEl)

                    self.gameSwf.removeElement(origEl)
                    self.gameSwf.replaceElement(modEl, origEl)
                    self.gameSwf.removeElement(modEl)
                    SetElementId(origEl, modElId)

                    self.gameSwf.symbolClass.setTag(modElId, anchor)

                    self.anchors.pop(anchor, None)
                    self.modifiedAnchorsMap.pop(anchor, None)

        if modHash in self.installed:
            self.installed.remove(modHash)

        if not fileOpen:
            self.close()


GAME_SWFS: Dict[str, GameSwf] = {}


def GetGameFileClass(gameFileName: str) -> Union[GameSwf, None]:
    return GAME_SWFS.get(gameFileName, None)


for _fileName, _filePath in BRAWLHALLA_SWFS.items():
    if "(" not in _fileName and "—" not in _fileName:
        GAME_SWFS[_fileName] = GameSwf(_filePath)
