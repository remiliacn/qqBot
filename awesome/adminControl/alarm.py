from json import loads, dump
from os import getcwd, mkdir
from os.path import exists


class Alarm:
    def __init__(self):
        self.global_alarm = {}
        self.temp_alarm = {}
        self.trigger = 0
        self.global_alarm = self._get_alarm()

    @staticmethod
    def _get_alarm() -> dict:
        if not exists(f'{getcwd()}/config'):
            mkdir(f'{getcwd()}/config')

        if exists(f'{getcwd()}/config/alarm.json'):
            with open('config/alarm.json', 'r') as file:
                return loads(file.read())

        with open(f'{getcwd()}/config/alarm.json', 'w+') as file:
            dump({}, file, indent=4)

        return {}

    def set_alarm(self, alarm: dict):
        self.trigger += 1
        if not self.global_alarm:
            if self.trigger >= 3:
                self.global_alarm = alarm
                self.update_alarm_stat()

    def get_alarm(self) -> dict:
        if self.trigger == 0 and self.global_alarm:
            self.clear_alarm()
            return {}

        return self.global_alarm

    def clear_alarm(self):
        self.global_alarm.clear()
        self.update_alarm_stat()
        self.trigger = 0

    def get_info(self):
        return f'警报优先等级：{self.global_alarm["sev"]}\n' \
               f'警报原因：{self.global_alarm["message"]}\n' \
               f'触发时间：{self.global_alarm["time"]}'

    def suppress_alarm(self):
        if self.trigger > 0:
            self.trigger -= 1

    def update_alarm_stat(self):
        with open('config/alarm.json', 'w+') as file:
            dump(self.global_alarm, file, indent=4)
