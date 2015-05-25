import sys
import time
import threading


class Spinner(threading.Thread):

    graphics = [
        "|,/,-,\\"
        ]

    def __init__(self, spinner_type=0, time_delay=0.1):

        self.ptr = 0
        self.delay = time_delay
        self.enabled = True
        self.symbols = Spinner.graphics[spinner_type].split(',')
        self.msg = ''
        threading.Thread.__init__(self)

    def run(self):

        while self.enabled:
            time.sleep(self.delay)
            sys.stdout.write("%s %s %s\n\r\x1b[A" % (self.symbols[self.ptr], self.msg, " "*20))
            if self.ptr < (len(self.symbols) - 1):
                self.ptr += 1
            else:
                self.ptr = 0

    def stop(self):
        self.enabled = False
        self.join()
        sys.stdout.write(" ")
