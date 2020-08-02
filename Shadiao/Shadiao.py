import requests, re, random, time, os

#临时图库，在网站不可用的时候使用里面的图片。
#github : remiliacn
baseDir = 'C:/Users/lvyiy/Pictures/表情包/'
INFO_NOT_AVAILABLE = "信息暂不可用"
headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"
}

class ShadiaoAPI:
    def __init__(self):
        random.seed(time.time_ns())
        self.Page = random.randint(0, 10)
        self.baseUrl = "https://www.fabiaoqing.com/biaoqing/lists/page/%s.html" % str(self.Page)
        self.ImageList = self.getImageList()

    def getImageList(self):
        global baseDir
        try:
            page = requests.get(self.baseUrl, timeout=15)
        except Exception as e:
            print("发表情网不可用：错误%s" % e)
            imageList = os.listdir(baseDir)
            return imageList

        imageList = re.findall(r'data-original="(.*?)"', page.text)
        return imageList

    def getPicture(self, downloadCount=1):

        random.seed(time.time_ns())
        imageList = self.ImageList

        fileList = []

        for count in range(downloadCount):
            index = random.randint(0, len(imageList) - 1)

            try:
                fileDetailedName = imageList[index].split('/')[-1]
                fileName = "D:/CQP/QPro/data/image/" + fileDetailedName
                if not os.path.exists(fileName):
                    img = requests.get(imageList[index], timeout=6)
                    img.raise_for_status()
                    with open(fileName, 'wb') as f:
                        f.write(img.content)

                print("Picture got:", fileName)
                if downloadCount > 1:
                    fileList.append(fileName)

                return fileName

            except Exception as e:
                imageList = os.listdir(baseDir)
                print("Exception occurred: %s" % e)
                if downloadCount == 1:
                    return baseDir + imageList[index]

        if len(fileList) > 0:
            return fileList

class XiaohuaAPI:
    def __init__(self):
        print("信息来源：笑话中关村网")
        random.seed(time.time_ns())
        self.baseUrl = 'http://xiaohua.zol.com.cn/jianduan/%d.html' % random.randint(0,3)
        self.jokeList = self.getJokeList()

    def getJokeList(self):
        global headers
        try:
            page = requests.get(self.baseUrl, headers=headers, timeout=10)
        except Exception as e:
            print("Something went wrong in getJokeList() %s" % e)
            jokeList = []
            return jokeList

        jokeList = re.findall(r'summary-text\">(.*?)</div', page.text)
        '''
        for n, i in enumerate(jokeList):
            jokeList[n] = re.sub(r'[\"sumarytex\-<>/div]+', '', jokeList[n])
        '''
        return jokeList

    def getJokeListEmpty(self):
        if len(self.jokeList) == 0:
            return True

        return False

    def getJoke(self, index=None):
        global INFO_NOT_AVAILABLE
        random.seed(time.time_ns())
        if self.getJokeListEmpty():
            return INFO_NOT_AVAILABLE

        if index is None:
            index = random.randint(0, len(self.jokeList) - 1)

        joke = self.jokeList[index]
        joke = re.sub(r'[&ldqo;]+', '"', joke)

        return joke

class ZhouInterprets:
    def __init__(self, keyWord):
        self.baseUrl = 'http://tools.2345.com/frame/dream/search'
        self.keyWord = keyWord
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        self.data = {
            'w': keyWord.encode('gbk'),
            'search_submit': '%BF%AA%CA%BC%BD%E2%C3%CE'
        }
        self.url = self._getUrl()

    def _getUrl(self):
        page = requests.post(self.baseUrl, headers=self.headers, data=self.data, timeout=10).text
        urlList = re.findall(r'<a href="(http://tools.2345.com/zhgjm/\d+\.htm)" target="_blank">.*?%s</a>' % self.keyWord, page)
        if len(urlList) == 0:
            urlList = re.findall(r'<a href="(/zhgjm/\d+\.htm)" target="_blank">.*?%s</a>' % self.keyWord, page)
            if len(urlList) == 0:
                return ''
            else:
                urlList[0] = 'https://tools.2345.com' + urlList[0]

        return urlList[0]

    def get_content(self):
        if self.url == '':
            return INFO_NOT_AVAILABLE

        syntax = re.compile('[&lrdquo;<st"ng>\u3000\t"p]+')
        page = requests.get(self.url, headers=headers, timeout=10).text
        contentList = re.findall(r'<p>(.*?)</p>', page)
        if len(contentList) < 10:
            count = -1
        else:
            count = 10

        response = ''
        for elements in contentList:
            if count == 0:
                break
            if re.match(r'.*?(扫码下载|周易解梦|由周公解梦 提供)', elements) or len(elements) < 5:
                response += ''
            else:
                elements = re.sub(syntax, '', elements)
                response += elements + '\n'
                count -= 1

        return response

class aValidator:
    def __init__(self, text):
        self.baseURL = f'https://www.libredmm.com/movies/{text}'
        self.torrentURL = 'https://idope.se/'
        self.pageText, self.status = self._getPageText()
        self.productNumber = text

    def _getPageText(self) -> (str, bool):
        try:
            page = requests.get(self.baseURL, timeout=15)
        except Exception as e:
            print("Timetout when fetching data %s" % e)
            return '', False
            
        if page.status_code == 200:
            return page.text, True

        return '', False

    def getContent(self) -> str:
        from lxml import etree
        if self.status:
            e = etree.HTML(self.pageText)
            title = e.xpath('/html/body/main/h1/span[2]/text()')[0]
            realTitle = ''
            if not title:
                title = '暂不可用'
            else:
                for elements in title:
                    realTitle += elements

                title = realTitle

            length = re.findall(r'<dd>(\d+.*?)</dd>', self.pageText)
            if length:
                length = length[0]
            else:
                length = '暂不可用'

            source = re.findall(r'<dd><a href="(.*?)"', self.pageText)
            if not source:
                source = '暂不可用'
            else:
                source = str(source[0]).replace('http://', '').replace('https://', '').replace('.', '点')

            torrentURL = self.torrentURL + f'/torrent-list/{self.productNumber}'
            try:
                page = requests.get(torrentURL, timeout=10)
            except Exception as e:
                return '连接出错'
                
            URLs = re.findall('<a href="(/torrent/.*?)"', page.text)
            if not URLs:
                tor = '暂不可用'
            else:
                try:
                    page = requests.get(self.torrentURL + URLs[0], timeout=10)
                except Exception as e:
                    return '连接出错'
                    
                tor = re.findall(r'<div id="deteails">(.*?)</div>', page.text)
                if not tor:
                    tor = '暂不可用'
                else:
                    tor = tor[0]

            return f'从番号{self.productNumber}我拿到了以下结果：\n' \
                   f'片名：{title}\n' \
                   f'时长：{length}\n' \
                   f'来源：{source}\n' \
                   f'磁链：{tor}'

        return f'未查到与番号"{self.productNumber}"相关的内容。'

import requests, time, re
class ticketFinder:
    def __init__(self):
        self.url2 = 'https://kyfw.12306.cn/otn/resources/js/framework/station_name.js?station_version=1.9142'
        self.json_data = {}
        _page = requests.get(self.url2)
        _cityInfo = _page.text
        _cityInfo = re.findall(r"'.*?'", _cityInfo)[0]
        _cities = _cityInfo.split('|')
        self.cityDictionary = {}
        for idx, element in enumerate(_cities):
            if (idx - 1) % 5 == 0 and idx + 1 != len(_cities):
                self.cityDictionary[_cities[idx]] = _cities[idx + 1]

    async def getTicket(self, fromWhere, toWhere, goTime):
        if fromWhere not in self.cityDictionary:
            return f'未找到输入城市：{fromWhere}！'
        if toWhere not in self.cityDictionary:
            return f'未找到输入城市：{toWhere}！'

        url = f'https://kyfw.12306.cn/otn/leftTicket/query?leftTicketDTO.train_date={goTime}&leftTicketDTO.from_station={self.cityDictionary[fromWhere]}&leftTicketDTO.to_station={self.cityDictionary[toWhere]}&purpose_codes=ADULT'
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Requested-With': 'XMLHttpRequest',
            'Cookie': f'RAIL_EXPIRATION={int(time.time()) + 86400000 * 3}; RAIL_DEVICEID=CcP_J5_0YblyYROGCFayi5lkxBM63_2_bSoVma_KM10nEDu5eh7TzkYBvz8V51WLwPjuMrx00N8o48pSgGiZOpLjGendhih0JNPpNj2H3_GuwuDH1ZN7kEa3Lpa_PTDFvOSz5ICmXpEYDrQukvx_sxmr75H9qYZ8; BIGipServerpool_passport=250413578.50215.0000; route=6f50b51faa11b987e576cdb301e545c4; _jc_save_fromStation=%u5317%u4EAC%2CBJP; _jc_save_toStation=%u4E0A%u6D77%2CSHH; _jc_save_toDate=2020-05-10; _jc_save_wfdc_flag=dc; _jc_save_fromDate=2020-05-10'

        }

        try:
            page = requests.get(url, headers=header, timeout=10)
            page.encoding = 'utf-8'
            self.json_data = page.json()
            result = self.json_data['data']['result']
            returnResult = ''
            for element in result:
                ticketInfo = element.split('|')
                returnResult += f'车次：{ticketInfo[3]}\t发车时间：{ticketInfo[8]} 到达时间：{ticketInfo[9]} 历时：{ticketInfo[10]} 商务座：{ticketInfo[32] if ticketInfo[32] != "" else "--"}， 一等座：{ticketInfo[31] if ticketInfo[31] != "" else "--"}，二等座：{ticketInfo[30] if ticketInfo[30] != "" else "--"}\n'

            return returnResult

        except Exception as e:
            return f'查询出错力！！'

