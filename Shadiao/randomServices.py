import requests, random, time

class Earthquakeinfo:
    def __init__(self):
        random.seed(time.time_ns())
        self.baseUrl = 'http://news.ceic.ac.cn/ajax/google?rand=%d' % random.randint(0, 5)
        self.earthDict = self._getEarthDict()

    def _getEarthDict(self):
        page = requests.get(self.baseUrl, timeout=10).json()
        return page[len(page) - 1]

    def get_newest_info(self):
        return '最新地震情况:\n' \
               '地震强度：%s级\n' \
               '发生时间（UTC+8):%s\n' \
               '纬度:%s°\n' \
               '经度:%s°\n' \
               '震源深度:%skm\n' \
               '震源位置:%s' % (self.earthDict['M'], self.earthDict['O_TIME'], self.earthDict['EPI_LAT'],
                            self.earthDict['EPI_LON'], self.earthDict['EPI_DEPTH'],
                            self.earthDict['LOCATION_C'])