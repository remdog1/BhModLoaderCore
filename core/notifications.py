from enum import Enum, auto


class NotificationType(Enum):
    ## Mods Sources
    # Loading
    LoadingModSource = auto()
    LoadingModSourceNew = auto()

    # Info
    CompileElementsCount = auto()

    # Compile
    CompileModSources = auto()
    CompileModSourcesImportActionScripts = auto()
    CompileModSourcesImportSound = auto()
    CompileModSourcesImportSprite = auto()
    CompileModSourcesImportPreview = auto()
    CompileModSourcesImportFile = auto()
    CompileModSourcesFinished = auto()

    # Errors
    CompileModSourcesSpriteHasNoSymbolclass = auto()
    CompileModSourcesSpriteEmpty = auto()
    CompileModSourcesSpriteNotFoundInFolder = auto()
    CompileModSourcesUnsupportedCategory = auto()
    CompileModSourcesUnknownFile = auto()

    CompileModSourcesSaveError = auto()

    ## Mods
    # Loading
    LoadingMod = auto()
    LoadingModData = auto()
    LoadingModCachePreviews = auto()

    # Info
    ModElementsCount = auto()
    ModConflict = auto()
    ModConflictSearchInSwf = auto()
    ModConflictNotFound = auto()

    # Installing
    ForceInstallation = auto()
    InstallingModSwf = auto()
    InstallingModSwfScript = auto()
    InstallingModSwfSound = auto()
    InstallingModSwfSprite = auto()
    InstallingModFile = auto()
    InstallingModFileCache = auto()

    InstallingModFinished = auto()

    # Uninstalling
    UninstallingModFile = auto()
    UninstallingModSwf = auto()
    UninstallingModSwfSound = auto()
    UninstallingModSwfSprite = auto()
    UninstallingModFinished = auto()

    # Warnings
    InstallingModInFileAlreadyInstalled = auto()  # If mod already installed in file

    # Errors
    LoadingModIsEmpty = auto()

    InstallingModNotFoundFileElement = auto()  # If not found file (jpg, mp3, png) in mod file
    InstallingModNotFoundGameSwf = auto()

    InstallingModSwfScriptError = auto()

    InstallingModSwfSoundSymbolclassNotExist = auto()  # If sound symbolclass not in game swf
    InstallingModSoundNotExist = auto()  # If sound not in mod file

    InstallingModSwfSpriteSymbolclassNotExist = auto()  # If sprite symbolclass not in game swf
    InstallingModSpriteNotExist = auto()  # If sprite not in mod file

    UninstallingModSwfOriginalElementNotFound = auto()
    UninstallingModSwfElementNotFound = auto()



class Notification:
    def __init__(self, notificationType: NotificationType, *args):
        self.notificationType = notificationType
        self.args = args

    def __repr__(self):
        return f"<{self.notificationType}: {self.args}>"
