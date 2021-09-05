from enum import Enum, auto


class Environment(Enum):
    SetModsPath = auto()
    SetModsSourcesPath = auto()
    ReloadMods = auto()
    ReloadModsSources = auto()
    GetModsData = auto()
    GetModsSourcesData = auto()

    GetModConflict = auto()
    InstallMod = auto()
    ForceInstallMod = auto()
    UninstallMod = auto()
    ReinstallMod = auto()

    CreateMod = auto()
    SetModName = auto()
    SetModAuthor = auto()
    SetModGameVersion = auto()
    SetModVersion = auto()
    SetModTags = auto()
    SetModDescription = auto()
    SetModPreviews = auto()
    SaveModSource = auto()
    CompileModSources = auto()

    Notification = auto()
