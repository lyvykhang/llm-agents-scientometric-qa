import threading
from threading import Thread, current_thread


class MyThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.parent = current_thread()
        Thread.__init__(self, *args, **kwargs)
