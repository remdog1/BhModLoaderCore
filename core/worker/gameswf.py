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
                             DefineTextTag,
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
        self.swfName = os.path.split(gameFilePath)[1]
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

    def importScript(self, content: str, scriptAnchor: str, modHash: str, createIfNotExists=False):
        """
        Import an ActionScript into the game SWF.
        
        Args:
            content: The ActionScript source code
            scriptAnchor: The fully qualified class name
            modHash: The mod hash installing this script
            createIfNotExists: If True, create a new script if it doesn't exist
            
        Returns:
            True if successful, False otherwise
        """
        fileOpen = self.gameSwf.isOpen()
        if not fileOpen:
            self.open()
        
        # Check if script exists
        origContent = self.gameSwf.getAS3(scriptAnchor)
        isNewScript = origContent is None
        
        if isNewScript:
            if not createIfNotExists:
                print(f"❌ Script '{scriptAnchor}' does not exist and createIfNotExists is False")
                if not fileOpen:
                    self.close()
                return False
            
            # Try to create new script (note: this may have limitations)
            print(f"✨ Creating NEW ActionScript class '{scriptAnchor}'")
            # For now, just log - AS3 creation is complex and may need manual intervention
            print(f"⚠️ ActionScript creation not fully implemented - script '{scriptAnchor}' may need to be added manually")
            if not fileOpen:
                self.close()
            return False
        else:
            # Clone orig script for backup
            if scriptAnchor not in self.scripts:
                self.scripts[scriptAnchor] = origContent

            success = self.gameSwf.setAS3(scriptAnchor, content)

            if success:
                self.modifiedAnchorsMap[scriptAnchor] = modHash
                if not fileOpen:
                    self.close()
                return True
            else:
                if not fileOpen:
                    self.close()
                return False

    def importSound(self, sound: DefineSoundTag, soundAnchor: str, modHash: str):
        fileOpen = self.gameSwf.isOpen()
        if not fileOpen:
            self.open()

        origSoundId = self.gameSwf.symbolClass.getTagByName(soundAnchor)
        if origSoundId is None:
            print(f"Error: Element '{soundAnchor}' not found!")
            return
        origSound = self.gameSwf.getElementById(origSoundId, DefineSoundTag)[0]

        # If orig not cloned
        if soundAnchor not in self.anchors:
            newOrigSoundId = self.gameSwf.getNextCharacterId()
            if self.gameSwf.symbolClass.getTag(newOrigSoundId) is not None:
                self.gameSwf.symbolClass.removeTag(newOrigSoundId)

            self.gameSwf.cloneAndAddElement(origSound, newOrigSoundId)
            self.anchors[soundAnchor] = newOrigSoundId

        cloneSound = sound.cloneTag()
        self.gameSwf.replaceElement(origSound, cloneSound)
        SetElementId(cloneSound, origSoundId)

        self.modifiedAnchorsMap[soundAnchor] = modHash

        if not fileOpen:
            self.close()

    def importSprite(self, sprite: DefineSpriteTag, spriteAnchor: str, modHash: str, elementsMap=None, createIfNotExists=False):
        """
        Import a sprite into the game SWF.
        
        Args:
            sprite: The DefineSpriteTag to import
            spriteAnchor: The symbol class name for the sprite
            modHash: The mod hash installing this sprite
            elementsMap: Map of element IDs (for internal use)
            createIfNotExists: If True, create a new sprite if it doesn't exist
            
        Returns:
            True if successful, False otherwise
        """
        fileOpen = self.gameSwf.isOpen()
        if elementsMap is None:
            elementsMap = {}
        cloneSprites = []
        cloneShapes = []

        if not fileOpen:
            self.open()

        origSpriteId = self.gameSwf.symbolClass.getTagByName(spriteAnchor)
        isNewSprite = origSpriteId is None
        
        if isNewSprite:
            if not createIfNotExists:
                print(f"Error: Element '{spriteAnchor}' not found!")
                return False
            
            # Create new sprite - assign a new character ID
            origSpriteId = self.gameSwf.getNextCharacterId()
            print(f"✨ Creating NEW sprite '{spriteAnchor}' with ID {origSpriteId}")
            
            # For new sprites, we'll add the sprite directly without needing an original
            origSprite = None
        else:
            origSprite = self.gameSwf.getElementById(origSpriteId, DefineSpriteTag)[0]

        # Remove modified sprite (only if it's not a new sprite)
        if not isNewSprite and spriteAnchor in self.anchors:
            for needElId in GetNeededCharactersId(origSprite):
                for needEl in self.gameSwf.getElementById(needElId):
                    self.gameSwf.removeElement(needEl)

        # For new sprites, we need to handle dependencies differently
        if isNewSprite:
            # Get needed characters from the sprite (from mod SWF, not game SWF)
            spriteSwf = GetSwfByElement(sprite)
            neededChars = GetNeededCharacters(sprite)
            
            # First, clone all dependencies
            for needElement in neededChars:
                needElId = GetElementId(needElement)
                if needElId not in elementsMap:
                    newElId = self.gameSwf.getNextCharacterId()
                    cloneEl = self.gameSwf.cloneAndAddElement(needElement, newElId)
                    
                    if self.gameSwf.symbolClass.getTag(newElId) is not None:
                        self.gameSwf.symbolClass.removeTag(newElId)
                    
                    elementsMap[needElId] = newElId
                    
                    if isinstance(cloneEl, DefineShapeTags):
                        if GetShapeBitmapId(cloneEl) is not None:
                            cloneShapes.append(cloneEl)
                    elif isinstance(cloneEl, DefineSpriteTag):
                        cloneSprites.append(cloneEl)
                    
                    # Handle font dependencies
                    if isinstance(cloneEl, DefineFontTags):
                        for dependentElement in spriteSwf.getElementById(needElId,
                                                                           (DefineFontNameTag,
                                                                            DefineFontAlignZonesTag)):
                            self.gameSwf.cloneAndAddElement(dependentElement, newElId)
                    
                    elif isinstance(cloneEl, DefineEditTextTag):
                        if dependentElement := spriteSwf.getElementById(needElId, CSMTextSettingsTag):
                            self.gameSwf.cloneAndAddElement(dependentElement[0], newElId)
                        if hasattr(needElement, 'fontId') and needElement.fontId in elementsMap:
                            cloneEl.fontId = elementsMap[needElement.fontId]
                    
                    elif isinstance(cloneEl, DefineTextTag):
                        if dependentElement := spriteSwf.getElementById(needElId, CSMTextSettingsTag):
                            self.gameSwf.cloneAndAddElement(dependentElement[0], newElId)
                        for textRecord in cloneEl.textRecords:
                            if textRecord.styleFlagsHasFont and hasattr(textRecord, 'fontId'):
                                if textRecord.fontId in elementsMap:
                                    textRecord.fontId = elementsMap[textRecord.fontId]
            
            # Now add the sprite itself
            newElId = origSpriteId
            cloneEl = sprite.cloneTag()
            self.gameSwf.addElement(cloneEl, newElId)
            
            # Add to symbol class
            if self.gameSwf.symbolClass.getTag(newElId) is not None:
                self.gameSwf.symbolClass.removeTag(newElId)
            self.gameSwf.symbolClass.addTag(newElId, spriteAnchor)
            
            elementsMap[GetElementId(sprite)] = newElId
            
            # Add to cloneSprites list for PlaceObject tag updates
            cloneSprites.append(cloneEl)
            
            print(f"✨ Added new sprite '{spriteAnchor}' to symbol class with ID {newElId}")
        else:
            # Existing sprite replacement logic (original code)
            for needElement in [*GetNeededCharacters(sprite), sprite]:
                if GetElementId(needElement) not in elementsMap:
                    if needElement == sprite:
                        # If orig cloned
                        if spriteAnchor not in self.anchors:
                            newOrigSpriteId = self.gameSwf.getNextCharacterId()
                            if self.gameSwf.symbolClass.getTag(newOrigSpriteId) is not None:
                                self.gameSwf.symbolClass.removeTag(newOrigSpriteId)

                            self.gameSwf.cloneAndAddElement(origSprite, newOrigSpriteId)
                            self.anchors[spriteAnchor] = newOrigSpriteId

                        newElId = origSpriteId
                        cloneEl = sprite.cloneTag()
                        self.gameSwf.replaceElement(origSprite, cloneEl)
                        SetElementId(cloneEl, origSpriteId)

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

                    if isinstance(cloneEl, DefineFontTags):
                        for dependentElement in GetSwfByElement(sprite).getElementById(GetElementId(needElement),
                                                                                       (DefineFontNameTag,
                                                                                        DefineFontAlignZonesTag)):
                            self.gameSwf.cloneAndAddElement(dependentElement, newElId)

                    elif isinstance(cloneEl, DefineEditTextTag):
                        if dependentElement := GetSwfByElement(sprite).getElementById(GetElementId(needElement),
                                                                                      CSMTextSettingsTag):
                            self.gameSwf.cloneAndAddElement(dependentElement[0], newElId)
                        if hasattr(needElement, 'fontId') and needElement.fontId in elementsMap:
                            cloneEl.fontId = elementsMap[needElement.fontId]

                    elif isinstance(cloneEl, DefineTextTag):
                        if dependentElement := GetSwfByElement(sprite).getElementById(GetElementId(needElement),
                                                                                      CSMTextSettingsTag):
                            self.gameSwf.cloneAndAddElement(dependentElement[0], newElId)

                        for textRecord in cloneEl.textRecords:
                            if textRecord.styleFlagsHasFont and hasattr(textRecord, 'fontId'):
                                if textRecord.fontId in elementsMap:
                                    textRecord.fontId = elementsMap[textRecord.fontId]

        for cloneSprite in cloneSprites:
            for sEl in cloneSprite.getTags().iterator():
                if isinstance(sEl, PlaceObject2Tag) and sEl.characterId > 0:
                    # Only update if the character ID exists in elementsMap
                    if sEl.characterId in elementsMap:
                        SetElementId(sEl, elementsMap[sEl.characterId])
                elif isinstance(sEl, PlaceObject3Tag) and sEl.characterId > 0:
                    # Only update if the character ID exists in elementsMap
                    if sEl.characterId in elementsMap:
                        SetElementId(sEl, elementsMap[sEl.characterId])

        for cloneShape in cloneShapes:
            bitmapId = GetShapeBitmapId(cloneShape)
            # Only update if the bitmap ID exists in elementsMap
            if bitmapId is not None and bitmapId in elementsMap:
                SetShapeBitmapId(cloneShape, elementsMap[bitmapId])

        self.modifiedAnchorsMap[spriteAnchor] = modHash

        if not fileOpen:
            self.close()
        
        return True

    def uninstallMod(self, modHash: str):
        SendNotification(NotificationType.UninstallingModSwf, modHash, os.path.split(self.gameSwf.swfPath)[1])

        fileOpen = self.gameSwf.isOpen()
        if not fileOpen:
            self.open()

        for anchor, _modHash in self.modifiedAnchorsMap.copy().items():
            if _modHash == modHash:

                # Repair script
                if anchor in self.scripts:
                    self.gameSwf.setAS3(anchor, self.scripts[anchor])

                    self.scripts.pop(anchor, None)
                    self.modifiedAnchorsMap.pop(anchor, None)

                    continue

                # Repair sounds and sprites
                origElId = self.anchors.get(anchor)
                if origElId is None:
                    #print(f"Error: Orig element '{anchor}' not found!")
                    SendNotification(NotificationType.UninstallingModSwfOriginalElementNotFound,
                                     _modHash, anchor, self.swfName)
                    continue
                origEl = self.gameSwf.getElementById(origElId)

                if origEl:
                    origEl = origEl[0]
                else:
                    print("Error: origEl = origEl[0]")
                    continue

                modElId = self.gameSwf.symbolClass.getTagByName(anchor)
                if modElId is None:
                    #print(f"Error: Mod element '{modElId}' not found!")
                    SendNotification(NotificationType.UninstallingModSwfElementNotFound,
                                     _modHash, anchor, self.swfName)
                    continue
                modEl = self.gameSwf.getElementById(modElId)

                if modEl:
                    modEl = modEl[0]
                else:
                    print("Error: modEl = modEl[0]")
                    continue

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
