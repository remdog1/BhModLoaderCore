import re
import os
from PIL import Image
from ..swf.swf import Swf, GetElementId
from ..worker.variables import CORE_VERSION
from ..worker.gameswf import GetGameFileClass
from ..worker.brawlhalla import BRAWLHALLA_PATH
from ..worker.brawlhalla import BRAWLHALLA_VERSION
from ..ffdec.classes import PlaceObject2Tag, DefineEditTextTag, CSMTextSettingsTag, MATRIX
from ..utils.hash import HashFile
from .config import ModloaderCoreConfig

TEMPLATE = '''
[
 xmin -40
 ymin -40
 xmax {xmax}
 ymax {ymax}
 readonly 1
 noselect 1
 html 1
 useoutlines 1
 font 2
 height 260
 color #ff{color1}
 align {align}
 leftmargin 0
 rightmargin 0
 indent 0
 leading 40
 ]<p align="{align}"><font face="Eras Demi ITC" size="{fontSize}" color="#{color2}" letterSpacing="0.00" kerning="1">{text}</font></p>
'''.strip()

UI_SCREEN_SOCIAL_HUB_MOD_V1_ID = "init_ScreenSocialHubV1"
BH_VERSION_TEXT = f"Brawlhalla: {BRAWLHALLA_VERSION}"


def _addText(swf: Swf, content: str, xmax, ymax, align="right", fontSize=13, color="#f7f8f9"):
    textId = swf.getNextCharacterId()
    text = DefineEditTextTag(swf._swf)
    # text.setFormattedText(None,
    #                       TEMPLATE.format(text=content, xmax=xmax, ymax=ymax, color1=color.strip("#"), align=align,
    #                                       fontSize=fontSize, color2=color.strip("#")),
    #                       None)
    swf.addElement(text, textId)

    CSM = CSMTextSettingsTag(swf._swf)
    CSM.textID = GetElementId(text)
    CSM.useFlashType = 1
    CSM.gridFit = 1 if align == "left" else 2
    CSM.setModified(True)
    swf.addElement(CSM)

    return textId


def _updateTextContent(textElem: DefineEditTextTag, newContent: str):
    newText = re.sub(r"(<font .+>).+(<\/font>)",
                     r"\1{}\2".format(newContent),
                     str(textElem.initialText))
    if newText != textElem.initialText:
        textElem.initialText = newText
        textElem.setModified(True)


def _addPlaceObjectTag(swf: Swf, sprite, setCharacterId, depth, name, index,
                       translateX=0, translateY=0, scaleX=None, scaleY=None):
    spriteMatrix = MATRIX(None)
    spriteMatrix.translateX = translateX
    spriteMatrix.translateY = translateY
    if scaleX is not None and scaleY is not None:
        spriteMatrix.hasScale = True
        spriteMatrix.scaleX = scaleX
        spriteMatrix.scaleY = scaleY

    spritePlace = PlaceObject2Tag(swf._swf)
    spritePlace.setCharacterId(setCharacterId)
    spritePlace.depth = depth
    spritePlace.placeFlagHasName = True
    spritePlace.name = name
    spritePlace.placeFlagHasMatrix = True
    spritePlace.matrix = spriteMatrix
    spritePlace.setModified(True)

    sprite.addTag(index, spritePlace)
    sprite.setModified(True)


def UninstallUIScreenSocialHubV1():
    gameSwf = GetGameFileClass("UI_ScreenSocialHub.swf")
    gameSwf.open()

    swf = gameSwf.gameSwf

    if UI_SCREEN_SOCIAL_HUB_MOD_V1_ID in gameSwf.installed:
        mainSprite = swf.getElementById(swf.symbolClass.getTagByName("a_ScreenSocialHub"))[0]
        spriteId = 0
        for tag in mainSprite.getTags().iterator():
            if isinstance(tag, PlaceObject2Tag) and tag.name == "am_PanelInternal":
                spriteId = tag.characterId
                break

        sprite = swf.getElementById(spriteId)[0]

        for tag in list(sprite.getTags().iterator()).copy():
            if isinstance(tag, PlaceObject2Tag):
                if tag.name == "v_bg":
                    pass
                    sprite.removeTag(tag)
                elif tag.name in ["v_bml", "v_bh"]:
                    sprite.removeTag(tag)
                    for elem in swf.getElementById(tag.characterId):
                        swf.removeElement(elem)

        sprite.setModified(True)

        gameSwf.installed.remove(UI_SCREEN_SOCIAL_HUB_MOD_V1_ID)
        gameSwf.save()

    gameSwf.close()


def InstallUIScreenSocialHubV1(bmlVersion):
    gameSwf = GetGameFileClass("UI_ScreenSocialHub.swf")
    gameSwf.open()

    swf = gameSwf.gameSwf

    # Update mod
    if UI_SCREEN_SOCIAL_HUB_MOD_V1_ID in gameSwf.installed:
        mainSprite = swf.getElementById(swf.symbolClass.getTagByName("a_ScreenSocialHub"))[0]
        spriteId = 0
        for tag in mainSprite.getTags().iterator():
            if isinstance(tag, PlaceObject2Tag) and tag.name == "am_PanelInternal":
                spriteId = tag.characterId
                break

        sprite = swf.getElementById(spriteId)[0]

        for tag in list(sprite.getTags().iterator()).copy():
            if isinstance(tag, PlaceObject2Tag):
                if tag.name == "v_bg":
                    pass
                elif tag.name == "v_bml":
                    for elem in swf.getElementById(tag.characterId, DefineEditTextTag):
                        _updateTextContent(elem, bmlVersion)
                elif tag.name == "v_bh":
                    for elem in swf.getElementById(tag.characterId, DefineEditTextTag):
                        _updateTextContent(elem, BH_VERSION_TEXT)

        sprite.setModified(True)

    # Install mod
    else:
        # BML Version text
        bmlTextId = _addText(swf, bmlVersion, 4200, 366)

        # Bh Version text
        bhTextId = _addText(swf, BH_VERSION_TEXT, 4200, 366)

        # Find sprite for editing
        mainSprite = swf.getElementById(swf.symbolClass.getTagByName("a_ScreenSocialHub"))[0]
        spriteId = 0
        for tag in mainSprite.getTags().iterator():
            if isinstance(tag, PlaceObject2Tag) and tag.name == "am_PanelInternal":
                spriteId = tag.characterId
                break

        sprite = swf.getElementById(spriteId)[0]
        startIndex = len(list(sprite.getTags().iterator())) - 1

        # Add background
        _addPlaceObjectTag(swf, sprite, swf.symbolClass.getTagByName("a_SocialHubCursor"), 9, "v_bg", startIndex,
                           -100, 1300, -66000, 60000)

        # Add bml version
        _addPlaceObjectTag(swf, sprite, bmlTextId, 10, "v_bml", startIndex + 1, -4350, 1350)

        # Add bh version
        _addPlaceObjectTag(swf, sprite, bhTextId, 11, "v_bh", startIndex + 2, -4350, 1650)

        gameSwf.installed.append(UI_SCREEN_SOCIAL_HUB_MOD_V1_ID)

    gameSwf.save()
    gameSwf.close()

from ..utils.hash import HashFile
from .config import ModloaderCoreConfig

def apply_loading_screen_overlay():
    try:
        brawlhalla_path = BRAWLHALLA_PATH
        if not brawlhalla_path:
            return

        ui_images_path = os.path.join(brawlhalla_path, "images", "UI")
        if not os.path.exists(ui_images_path):
            return

        overlay_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'ui', 'ui_sources', 'resources', 'images', 'Modloader_UI_overlay.png'))
        if not os.path.exists(overlay_path):
            return

        # Get all loading screen files
        loading_screen_files = []
        for filename in os.listdir(ui_images_path):
            if filename.startswith("UIBackgroundBitmapLoading") and filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                loading_screen_files.append(filename)

        # Check for removed files and clean up config
        for stored_file in list(ModloaderCoreConfig.loadingScreenChecksums.keys()):
            if stored_file not in loading_screen_files:
                del ModloaderCoreConfig.loadingScreenChecksums[stored_file]
                ModloaderCoreConfig.save()

        # Process each loading screen
        for filename in loading_screen_files:
            loading_screen_path = os.path.join(ui_images_path, filename)
            current_hash = HashFile(loading_screen_path)
            original_hash = ModloaderCoreConfig.loadingScreenChecksums.get(filename)

            # If file is new or has been reverted by a game update
            if original_hash is None or original_hash == current_hash:
                
                # If it's a new file, store its original hash
                if original_hash is None:
                    ModloaderCoreConfig.loadingScreenChecksums[filename] = current_hash
                    ModloaderCoreConfig.save()

                # Apply the overlay
                background = Image.open(loading_screen_path).convert("RGBA")
                overlay = Image.open(overlay_path).convert("RGBA")

                bg_width, bg_height = background.size
                ov_width, ov_height = overlay.size
                position = (bg_width - ov_width - 60, bg_height - ov_height - 10)

                combined = Image.new("RGBA", background.size)
                combined.paste(background, (0,0))
                combined.paste(overlay, position, overlay)

                if loading_screen_path.lower().endswith(('.jpg', '.jpeg')):
                    final_image = combined.convert('RGB')
                    final_image.save(loading_screen_path, quality=100)
                else:
                    combined.save(loading_screen_path, compress_level=1)

    except Exception:
        # Silently fail to not interrupt the user
        pass



def InstallBaseMod(firstText=None):
    if firstText is None:
        firstText = f"Brawlhalla ModLoader Core: {CORE_VERSION}"

    InstallUIScreenSocialHubV1(firstText)
    apply_loading_screen_overlay()
