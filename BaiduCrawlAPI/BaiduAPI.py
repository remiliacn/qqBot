import requests, re, logging, time
from lxml import etree

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"
}

INFO_NOT_AVAILABLE = "信息暂不可用"

class BaiduWeatherAPI:
    def __init__(self, city):

        self.City = city
        self.Weather = INFO_NOT_AVAILABLE
        self.Temp = INFO_NOT_AVAILABLE
        self.Wind = INFO_NOT_AVAILABLE
        self.Msg = INFO_NOT_AVAILABLE
        self.BaseUrl = 'http://www.baidu.com/s?ie=utf-8&wd='
        self.Page = self.getCityWeatherInformation()

    def getCityWeatherInformation(self):
        print("数据来源：百度天气")
        self.BaseUrl = self.BaseUrl + self.City + '天气'
        page = requests.get(self.BaseUrl)
        try:
            pages = page.content.decode('utf-8')
        except UnicodeDecodeError:
            pages = page.text

        return pages

    def getCityTemperature(self):

        e = etree.HTML(self.Page)

        tempList = e.xpath('//*[@id="1"]/div[1]/div/a[1]/p[2]/text()')
        if len(tempList) != 0:
            self.Temp = str(tempList[0])

        return self.Temp

    def getCityWeather(self):
        e = etree.HTML(self.Page)
        tempList = str(e.xpath('//*[@id="1"]/div[1]/div/a[1]/p[3]/text()'))

        try:
            weather_temp = re.findall(r'[\u4e00-\u9fff]+', tempList)[0]
            self.Weather = weather_temp

        except Exception as e:
            print("No result found with this city name: " + self.City)
            logging.debug("error " + e)

        finally:
            return self.Weather

    def getCity(self):
        e = etree.HTML(self.Page)
        tempList = e.xpath('//*[@id="1"]/h3/a/em[1]/text()')
        if len(tempList) != 0:
            self.Msg = tempList[0]

        return self.Msg

    def getCityWind(self):
        e = etree.HTML(self.Page)
        tempList = e.xpath('//*[@id="1"]/div[1]/div/a[1]/p[4]/text()')
        if len(tempList) != 0:
            self.Wind = str(tempList[0])

        return self.Wind

    def getString(self):

        response = INFO_NOT_AVAILABLE
        if self.getCity() != INFO_NOT_AVAILABLE:
            response = "查询信息:" + "\n" + self.getCity() + \
                       "\n温度：" + self.getCityTemperature() + \
                       "\n天气：" + self.getCityWeather() + \
                       "\n风向：" + self.getCityWind()

        return response


class BaiduNewsAPI:
    def __init__(self):
        self.baseUrl = 'http://news.baidu.com/'
        self.titleList = []
        self.titleList, self.pageContent = self.getNewsList()
        self.title = ''
        self.emptyList = self.getNewsEmpty()

    def getNewsList(self):
        print("数据来源：百度新闻")
        startTime = time.time()
        if len(self.titleList) == 0:
            baseUrl = self.baseUrl
            try:
                page = requests.get(baseUrl, timeout=10)
            except requests.exceptions.ReadTimeout:
                logging.debug('timeout Error in getNewsList%s')
                return [], ''

            page = page.text
            e = etree.HTML(page)

            tempList = e.xpath('//*[@id="pane-news"]/ul/li/a/text()')
            self.titleList = tempList.copy()
            indexTemp = 0

            for index, element in enumerate(tempList, start=0):
                if len(element) <= 5:
                    del self.titleList[index + indexTemp]
                    indexTemp -= 1

        print("耗时：%fs" % (time.time() - startTime))

        return self.titleList, page

    def getNewsListString(self):
        response = INFO_NOT_AVAILABLE
        if not self.getNewsEmpty():
            response = ''
            index = 1
            for element in self.titleList:
                response += '%d、%s\n' % (index, element)
                index += 1

        return response

    def getNewsEmpty(self):
        if len(self.titleList) == 0:
            return True

        return False

    def getNewsURL(self, index):
        global INFO_NOT_AVAILABLE
        if index > len(self.titleList) or index == 0:
            return INFO_NOT_AVAILABLE, INFO_NOT_AVAILABLE

        if index > 0:
            index -= 1

        self.title = self.titleList[index]
        url = re.findall(r'[https]{4,}://.*?%s' % self.titleList[index][0:5], self.pageContent)
        if len(url) != 0:
            url = re.findall(r'https?://.*?\"', url[0])[0]
            url = url[0:len(url) - 1]

        else:
            url = INFO_NOT_AVAILABLE

        return url, self.title

    def getNewsReport(self, index):
        url, title = self.getNewsURL(index=index)
        content = self.getNewsContent(url=url)
        return "您所查询的新闻是：%s" \
               "\n其所在页面为：%s" \
               "\n新闻内容为：\n%s" % (title, url, content)

    def getNewsReportByKeyWord(self, keyWord):
        index = -1
        for idx, element in enumerate(self.titleList):
            if re.match(r'.*?%s' % keyWord, element):
                index = idx
                break

        return index + 1

    def getNewsContent(self, url):
        startTime = time.time()
        global INFO_NOT_AVAILABLE
        if url == INFO_NOT_AVAILABLE:
            return INFO_NOT_AVAILABLE
        try:
            page = requests.get(url, headers=headers, timeout=5)
            page = page.content.decode('utf-8')
            e = etree.HTML(page)
            response = ''
            if re.match(r'.*?baijiahao', url):
                content = e.xpath('//*[@id="article"]/div/p/span/text()')

            elif re.match(r'.*?huanqiu', url):
                content = e.xpath('//*[@id="article"]/div[2]/p/text()')

            elif re.match(r'.*?xinhuanet', url):
                content = e.xpath('//*[@id="p-detail"]/div[2]/p/text()')
                if len(content) == 0:
                    content = e.xpath('//*[@id="p-detail"]/p/text()')

            else:
                content = []

            if len(content) == 0:
                response = '数据暂时无法读取'
                return response

            for element in content:
                if len(element) > 2:
                    response += element + '\n'
        except TimeoutError:
            response = INFO_NOT_AVAILABLE

        print("耗时：%fs" % (time.time() - startTime))
        return response


class BaiduLeaderBoard:
    def __init__(self):
        startTime = time.time()
        self.baseUrl = 'http://www.baidu.com/s?ie=utf-8&wd=abc'
        self.leaderBoard, self.clickData = self.getBoardList()
        print("耗时%fs" % (time.time() - startTime))

    def getBoardList(self):
        boardList = []
        clickList = []
        try:
            page = str(requests.get(self.baseUrl, headers=headers, timeout=10).content.decode('utf-8'))
        except requests.exceptions.RequestException:
            logging.warning("Something went wrong when getBoardList()")
            return boardList, clickList

        e = etree.HTML(page)
        boardList = e.xpath('//*[@id="con-ar"]/div/div/div/table/tbody[1]/tr/td[1]/span/a/text()')
        clickList = e.xpath('//*[@id="con-ar"]/div/div/div/table/tbody[1]/tr/td[2]/text()')

        if len(boardList) != len(clickList):
            logging.warning("Something went wrong when getBoardList()")
            return [], []

        return boardList, clickList

    def refreshBoard(self):
        self.leaderBoard, self.clickData = self.getBoardList()

    def checkInit(self):
        return checkEmpty(self.leaderBoard)

    def toString(self):
        response = ''
        if self.leaderBoard is [] or self.clickData is []:
            return INFO_NOT_AVAILABLE
        for index, element in enumerate(self.leaderBoard):
            response += '%d、标签：%s\t点击量：%s\n' % ((index + 1), element, self.clickData[index])

        return response

    def getNewsContent(self, keyWord):
        startTime = time.time()
        idx = -1
        for index, element in enumerate(self.leaderBoard):
            if re.match(r'.*?%s' % keyWord, element):
                idx = index
                keyWord = element
                break

        if idx != -1:
            page = requests.get('https://search.sina.com.cn/?q=%s&c=news&from=channel&ie=utf-8' % keyWord,
                                headers=headers).text

            getHref = re.findall(r'https?://k\.sina\.com\.cn/article[a-zA-Z0-9_\?\.=&]+', page)
            if checkEmpty(getHref):
                getHref = re.findall(r'https://news\.sina\.com\.cn.*?html', page)

            if checkEmpty(getHref):
                return INFO_NOT_AVAILABLE

            for element in getHref:

                page = requests.get(element, headers=headers).content.decode('utf-8')
                e = etree.HTML(page)
                contentList = e.xpath('//*[@id="artibody"]/p/font/text()')
                if len(contentList) > 0:
                    break

            response = ''
            if checkEmpty(contentList):
                return INFO_NOT_AVAILABLE

            for element in contentList:
                response += element + '\n'

            print("耗时%fs" % (time.time() - startTime))

            return response

        return INFO_NOT_AVAILABLE


class NewsSearch:
    def __init__(self, keyWord):
        self.keyWord = keyWord
        self.baseUrl = 'https://search.sina.com.cn/?q=%s&c=news&from=channel&ie=utf-8' % keyWord
        self.titleList, self.urlList = self.getTitles()

    def getTitles(self):
        page = requests.get(self.baseUrl, headers=headers).text
        e = etree.HTML(page)
        temptitleList = e.xpath('//*[@id="result"]/div/h2//text()')
        titleList = []
        str = ''
        for element in temptitleList:
            if not re.match(r'.*?\n', element) and not re.match(r'.*?%s' % time.strftime("%Y-%m-%d", time.localtime()),
                                                                element):
                str += element
            else:
                temptitleList.remove(element)
                titleList.append(str)
                str = ''

        urlListTemp = re.findall(r'https?://[kvnews]+\.sina\.com\.cn/[\.a-zA-Z0-9_\?\.=/\-&]+', page)
        urlList = []
        for i in urlListTemp:
            if i not in urlList:
                urlList.append(i)

        return titleList, urlList

    def getTitleString(self):
        count = 1
        response = ''
        if checkEmpty(self.titleList):
            response = INFO_NOT_AVAILABLE

        else:
            for element in self.titleList:
                response += '%d、%s\n' % (count, element)
                count += 1

        return response

    def initCheck(self):
        return checkEmpty(self.titleList)

    def getNewsContent(self, keyWord):
        if checkEmpty(self.titleList):
            return INFO_NOT_AVAILABLE

        idx = -1
        url = ''
        for index, element in enumerate(self.titleList):
            if re.match(r'.*?%s' % keyWord, element):
                idx = index
                url = self.urlList[idx]
                break

        if url == '' or idx == -1:
            return INFO_NOT_AVAILABLE

        logging.warning("DEBUG: %s" % url)
        try:
            page = requests.get(url)
            page = page.content.decode('utf-8')
        except UnicodeDecodeError:
            page = page.text

        e = etree.HTML(page)
        contentList = e.xpath('//*[@id="artibody"]/p/font/text()')
        if checkEmpty(contentList):
            contentList = e.xpath('//*[@id="article"]//text()')

        if checkEmpty(contentList):
            return "%s\n新闻网站：%s" % (INFO_NOT_AVAILABLE, url)

        content = ''
        for element in contentList:
            if not re.match(r'[\n\t]', element):
                content += element + '\n'

        return content

    def getContentByIndex(self, index=-1):
        if index == -1:
            return INFO_NOT_AVAILABLE

        try:
            page = requests.get(self.urlList[index - 1])
            page = page.content.decode('utf-8')
        except UnicodeDecodeError:
            page = page.text

        e = etree.HTML(page)
        contentList = e.xpath('//*[@id="artibody"]/p/font/text()')
        if checkEmpty(contentList):
            contentList = e.xpath('//*[@id="article"]//text()')

        if checkEmpty(contentList):
            return "%s\n新闻网站：%s" % (INFO_NOT_AVAILABLE, self.urlList[index - 1])

        content = ''
        for element in contentList:
            if not re.match(r'[\n\t]', element):
                content += element + '\n'

        return content


def checkEmpty(checkList):
    if len(checkList) == 0:
        return True

    return False
