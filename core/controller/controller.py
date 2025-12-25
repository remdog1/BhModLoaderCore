import multiprocessing
import sys
import os

from ..commands import Environment
from ..notifications import Notification


def run_server_process(recv_queue: multiprocessing.Queue, send_queue: multiprocessing.Queue):
    # Define a log file path.
    log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'worker_error.log'))
    # Clear previous log file
    if os.path.exists(log_path):
        try:
            os.remove(log_path)
        except OSError:
            pass  # Ignore if we can't remove it, we'll overwrite it anyway
        
    log_file = open(log_path, 'w', encoding='utf-8')
    # Redirect stdout and stderr
    sys.stdout = log_file
    sys.stderr = log_file

    try:
        from ..worker.dispatch import Dispatch
        from ..worker.basedispatch import SetDispatchQueue

        server_thread = Dispatch()
        SetDispatchQueue(recv_queue, send_queue)
        server_thread.start()
        server_thread.join()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        # Ensure the log file is closed so the main process can access it
        log_file.close()


class BaseController:
    _server_process = None
    _send_queue = None
    _recv_queue = None

    def __init__(self):
        if self.__class__._server_process is None:
            self.__class__._send_queue = multiprocessing.Queue()
            self.__class__._recv_queue = multiprocessing.Queue()

            self.run_server()

    def run_server(self):
        multiprocessing.freeze_support()
        self.__class__._server_process = multiprocessing.Process(target=run_server_process,
                                                       args=(self._send_queue, self._recv_queue),
                                                       daemon=True)
        self.__class__._server_process.start()

        # Wait for the launch of the process
        if self.receive_wait() != 0x1:
            # The worker crashed. Let's read the log file.
            log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'worker_error.log'))
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    error_log = f.read()
                    # Print to the actual console, not the redirected one
                    print(f"--- Worker Process Error Log ---\\{error_log}\n--------------------------------", file=sys.__stderr__)
            raise Exception("Error: Worker process failed to start. See log above.")

    @property
    def ready_to_receive(self) -> bool:
        return not self._recv_queue.empty()

    def receive(self):
        data = self._recv_queue.get(False)
        return data

    def receive_wait(self):
        return self._recv_queue.get()

    def send(self, data):
        self._send_queue.put(data, False)

    def sendEnv(self, env: Environment, *args):
        self.send([env, *args])

    def getData(self):
        if self.ready_to_receive:
            return self.receive()
        else:
            return None


class Controller(BaseController):
    def setModsPath(self, path):
        self.sendEnv(Environment.SetModsPath, path)

    def setModsSourcesPath(self, path):
        self.sendEnv(Environment.SetModsSourcesPath, path)

    def reloadMods(self):
        self.sendEnv(Environment.ReloadMods)

    def reloadModsSources(self):
        self.sendEnv(Environment.ReloadModsSources)

    def getModsData(self):
        self.sendEnv(Environment.GetModsData)

    def getModsSourcesData(self):
        self.sendEnv(Environment.GetModsSourcesData)

    def installBaseMod(self, text):
        self.sendEnv(Environment.InstallBaseMod, text)

    def getModConflict(self, hash):
        self.sendEnv(Environment.GetModConflict, hash)

    def installMod(self, hash):
        self.sendEnv(Environment.InstallMod, hash)

    def uninstallMod(self, hash):
        self.sendEnv(Environment.UninstallMod, hash)

    def reinstallMod(self, hash):
        self.sendEnv(Environment.ReinstallMod, hash)

    def decompileMod(self, hash):
        self.sendEnv(Environment.DecompileMod, hash)

    def deleteMod(self, hash):
        self.sendEnv(Environment.DeleteMod, hash)

    def forceInstallMod(self, hash):
        self.sendEnv(Environment.ForceInstallMod, hash)

    def createMod(self, folderName):
        self.sendEnv(Environment.CreateMod, folderName)

    def setModName(self, hash, name):
        self.sendEnv(Environment.SetModName, hash, name)

    def setModAuthor(self, hash, author):
        self.sendEnv(Environment.SetModAuthor, hash, author)

    def setModGameVersion(self, hash, gameVersion):
        self.sendEnv(Environment.SetModGameVersion, hash, gameVersion)

    def setModVersion(self, hash, version):
        self.sendEnv(Environment.SetModVersion, hash, version)

    def setModTags(self, hash, tags):
        self.sendEnv(Environment.SetModTags, hash, tags)

    def setModDescription(self, hash, description):
        self.sendEnv(Environment.SetModDescription, hash, description)

    def setModPreviews(self, hash, previews):
        self.sendEnv(Environment.SetModPreviews, hash, previews)

    def saveModSource(self, hash):
        self.sendEnv(Environment.SaveModSource, hash)

    def compileModSources(self, hash):
        self.sendEnv(Environment.CompileModSources, hash)

    def deleteModSources(self, hash):
        self.sendEnv(Environment.DeleteModSources, hash)
