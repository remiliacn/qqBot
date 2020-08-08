from time import time

class Metrics:
    def __init__(self):
        self.Metrics = {}

class StopWatch:
    def __init__(self):
        self.stop_watch_list = {}

    def stop_watch_start(self, metrics):
        start_time = time()
        if metrics in self.stop_watch_list:
            if self.stop_watch_list[metrics]['isRunning']:
                raise StopWatchException('Stop watch started failed. ',
                                         f'Instance: {metrics} has already started.')

        self.stop_watch_list[metrics] = {
            'startTime' : start_time,
            'isRunning' : True
        }

    def stop_watch_end(self, metrics) -> int:
        if metrics not in self.stop_watch_list:
            raise StopWatchException('Stop watch ended failed.',
                                     f'Instance: {metrics} does not exist in current context.')

        if not self.stop_watch_list[metrics]['isRunning']:
            raise StopWatchException('Stop watch ended failed.',
                                     f'Instance: {metrics} did not start running yet.')

        stop_time = time() - self.stop_watch_list[metrics]['startTime']
        self.stop_watch_list[metrics]['isRunning'] = False
        return int(stop_time)

class StopWatchException:
    def __init__(self, expression, error_message):
        self.expression = expression
        self.errorMessage = error_message
