import threading

from .basedispatch import BaseDispatch, Index
from .variables import *
from .modloader import ModLoader

from ..commands import Environment


class Dispatch(BaseDispatch):
    @Index(Environment.SetModsPath)
    def setModPath(self, path):
        SetModsPath(path)
        return True

    @Index(Environment.SetModsSourcesPath)
    def setModsSourcesPath(self, path):
        SetModsSourcesPath(path)
        return True

    @Index(Environment.ReloadMods)
    def reloadMods(self):
        ModLoader.reloadMods()
        return True

    @Index(Environment.ReloadModsSources)
    def reloadModsSources(self):
        ModLoader.reloadModsSources()
        return True

    @Index(Environment.GetModsData)
    def getModsData(self):
        return ModLoader.getModsData()

    @Index(Environment.GetModsSourcesData)
    def getModsSourcesData(self):
        return ModLoader.getModsSourcesData()

    @Index(Environment.GetModConflict)
    def getModConflict(self, hash):
        mod = ModLoader.getModByHash(hash)
        if mod is not None:
            threading.Thread(target=mod.getModConflict).start()
            #mod.getModConflict()

            return True, hash

        return False, None

    @Index(Environment.InstallMod)
    def installMod(self, hash):
        mod = ModLoader.getModByHash(hash)
        if mod is not None:
            threading.Thread(target=mod.install, kwargs={"forceInstallation": True}).start()
            #mod.install()
            return True, hash

        return False, None

    @Index(Environment.ForceInstallMod)
    def forceInstallMod(self, hash):
        mod = ModLoader.getModByHash(hash)
        if mod is not None:
            threading.Thread(target=mod.install, kwargs={"forceInstallation": True}).start()
            # mod.install()
            return True, hash

        return False, None

    @Index(Environment.UninstallMod)
    def uninstallMod(self, hash):
        mod = ModLoader.getModByHash(hash)
        if mod is not None:
            threading.Thread(target=mod.uninstall).start()
            #mod.uninstall()
            return True, hash

        return False, None

    @Index(Environment.DeleteMod)
    def deleteMod(self, hash):
        mod = ModLoader.getModByHash(hash)
        if mod is not None:
            ModLoader.modsClasses.remove(mod)
            mod.delete()
            del mod
            # mod.uninstall()
            return True, hash

        return False, None

    @Index(Environment.ReinstallMod)
    def reinstallMod(self, hash):
        mod = ModLoader.getModByHash(hash)
        if mod is not None:
            mod.reinstall()
            return True, hash

        return False

    @Index(Environment.CreateMod)
    def createMod(self, folderName):
        modSource = ModLoader.createModSource(folderName)
        if modSource is not None:
            for modSourcesData in ModLoader.getModsSourcesData():
                if modSourcesData["hash"] == modSource.hash:
                    return True, modSourcesData

        return False, None

    @Index(Environment.SetModName)
    def setModName(self, hash, name):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            modSources.setName(name)
            return True, hash

        return False, None

    @Index(Environment.SetModAuthor)
    def setModAuthor(self, hash, author):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            modSources.setAuthor(author)
            return True, hash

        return False, None

    @Index(Environment.SetModGameVersion)
    def setModGameVersion(self, hash, gameVersion):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            modSources.setGameVersion(gameVersion)
            return True, hash

        return False, None

    @Index(Environment.SetModVersion)
    def setModVersion(self, hash, version):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            modSources.setVersion(version)
            return True, hash

        return False, None

    @Index(Environment.SetModTags)
    def setModTags(self, hash, tags):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            modSources.setTags(tags)
            return True, hash

        return False, None

    @Index(Environment.SetModDescription)
    def setModDescription(self, hash, description):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            modSources.setDescription(description)
            return True, hash

        return False, None

    @Index(Environment.SetModPreviews)
    def setModPreviews(self, hash, previews):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            modSources.setPreviewsPaths(previews)
            return True, hash

        return False, None

    @Index(Environment.SaveModSource)
    def saveModSource(self, hash):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            modSources.saveModData()
            return True, hash

        return False, None

    @Index(Environment.CompileModSources)
    def compileModSources(self, hash):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            threading.Thread(target=modSources.compile).start()
            return True, hash

        return False, None

    @Index(Environment.DeleteModSources)
    def deleteModSources(self, hash):
        modSources = ModLoader.getModSourcesByHash(hash)
        if modSources is not None:
            ModLoader.modsSources.remove(modSources)
            modSources.delete()
            del modSources
            # mod.uninstall()
            return True, hash

        return False, None
