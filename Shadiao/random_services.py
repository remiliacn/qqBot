import requests, random, time

class Earthquakeinfo:
    def __init__(self):
        random.seed(time.time_ns())
        self.base_url = 'http://news.ceic.ac.cn/ajax/google?rand=%d' % random.randint(0, 5)
        self.earth_dict = self._get_earth_dict()

    def _get_earth_dict(self):
        page = requests.get(self.base_url, timeout=10).json()
        return page[len(page) - 1]

    def get_newest_info(self):
        return '最新地震情况：\n' \
               '地震强度：%s级\n' \
               '发生时间（UTC+8)：%s\n' \
               '纬度：%s°\n' \
               '经度：%s°\n' \
               '震源深度：%skm\n' \
               '震源位置：%s' % (self.earth_dict['M'], self.earth_dict['O_TIME'], self.earth_dict['EPI_LAT'],
                            self.earth_dict['EPI_LON'], self.earth_dict['EPI_DEPTH'],
                            self.earth_dict['LOCATION_C'])
