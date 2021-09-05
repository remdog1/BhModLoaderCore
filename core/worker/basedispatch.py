import threading
import multiprocessing

from ..commands import Environment
from ..notifications import Notification, NotificationType


_dispatchMap = {}


def Index(env):
    def caller(method):
        def runner(self, *args, **kwargs):
            returns = method(self, *args, **kwargs)
            if isinstance(self, BaseDispatch):
                self.sendEnv(env, returns)

        _dispatchMap[env] = runner

        return runner

    return caller


def SetDispatchQueue(recv_queue: multiprocessing.Queue, send_queue: multiprocessing.Queue):
    if BaseDispatch._recv_queue is None:
        BaseDispatch._recv_queue = recv_queue
    if BaseDispatch._send_queue is None:
        BaseDispatch._send_queue = send_queue


class BaseDispatch(threading.Thread):
    _recv_queue = None
    _send_queue = None

    runThread = None

    def __init__(self):
        if self.runThread is None:
            super().__init__(daemon=True)

    def run(self):
        BaseDispatch.runThread = self

        self.send(0x1)

        self.listener()

    @property
    def ready_to_receive(self) -> bool:
        return not self._recv_queue.empty()

    def receive(self):
        return self._recv_queue.get(False)

    def receive_wait(self):
        return self._recv_queue.get()

    def send(self, data):
        self._send_queue.put(data, False)

    def sendEnv(self, env: Environment, *args):
        self.send([env, *args])

    def listener(self):
        while True:
            self._dispatch(self.receive_wait())

    def _dispatch(self, data):
        #print(f"Controller -> {str(data)}\n", end="")
        if isinstance(data, list):
            if len(data) == 0:
                return

            elif method := _dispatchMap.get(data[0], None):
                method(self, *data[1:])

    def sendNotification(self, notification: Notification):
        self.sendEnv(Environment.Notification, notification)


def SendNotification(notificationType: NotificationType, *args):
    BaseDispatch.runThread.sendNotification(Notification(notificationType, *args))
