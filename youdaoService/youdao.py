import requests, re, logging
from lxml import etree

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"
}

class Youdaodict:
    def __init__(self, keyWord):
        self.baseUrl = 'http://dict.youdao.com/w/jap/'
        self.keyWord = keyWord
        self.Page = self.getPageText()
        self.webList = []
        self.explainList = self.getExplainations()

    def getPageText(self):
        url = self.baseUrl + self.keyWord
        try:
            page = requests.get(url, headers=headers, timeout=15)
        except TimeoutError:
            page = ''

        return page.text

    def getExplainations(self):
        e = etree.HTML(self.Page)
        self.explainList = re.findall(r'<p class="sense-title">(.*?)</p>', self.Page)
        if len(self.explainList) == 0:
            self.getWebExplain(e)
        else:
            self.explainList.append('----网络释义----')
            self.explainList = re.findall(r'[^\\t\s\\n\'\[\],]+', str(self.explainList))
            self.getWebExplain(e)

        return self.explainList

    def getWebExplain(self, e):
        self.webList = e.xpath('//*[@id="tWebTrans"]/div/div/span/text()')
        if len(self.webList) > 0:
            self.webList = re.findall(u"[\u30a0-\u30ff\u4e00-\u9fa5]+", str(self.webList))
            for elements in self.webList:
                if elements != '更多' and elements != '收起' and elements not in self.explainList:
                    self.explainList.append(elements)

    def explain_to_string(self):
        if len(self.explainList) == 0:
            return '查词出错惹！！'

        feedBack = ''
        for elements in self.explainList:
            feedBack += '%s\n' %  elements

        return feedBack

class Goodict:
    def __init__(self, keyWord):
        self.baseUrl = 'http://dictionary.goo.ne.jp/srch/jn/%s/m0u/' % keyWord
        self.hostUrl = 'http://dictionary.goo.ne.jp'
        self.CONNECTION_FAILED = '连接出错！！'
        self.INFO_NOT_AVAILABLE = '未找到翻译结果！'
        self.doNewLine = False
        self.Page = self._request()
        self.titleList = self.getTitleList()
        self.urlList= self.getUrl()
        self.explaination = []
        self.transList = []

    def _request(self):
        try:
            page = requests.get(self.baseUrl, headers=headers, timeout=15)
        except Exception as e:
            return self.CONNECTION_FAILED + str(e)

        return page.text

    def getTitleList(self):
        e = etree.HTML(self.Page)
        try:
            titleList = e.xpath('//*[@id="NR-main"]/section/div/section/div/ul/li/a/dl/dt/text()')
        except Exception as e:
            logging.warning('Something went horribly wrong!')
            return []
        syntax = re.compile(r'[\n\t\s]+')
        for idx, elements in enumerate(titleList):
            titleList[idx] = re.sub(syntax, '', elements)

        return titleList


    def getUrl(self):
        urlList = re.findall(r'<a href=\"/(.*?)\"', self.Page)

        urlList2 = []
        for elements in urlList:
            if re.match(r'word/.*?/#jn-\d+', elements) or re.match(r'jn/\d+/meaning/m[0-9]u/.*?/', elements):
                urlList2.append(elements)

        if len(urlList2) == 0:
            urlList = re.findall(r'<a href=\"(http://wpedia\.goo\.ne\.jp/wiki/.*?)\"', self.Page)
            for elements in urlList:
                urlList2.append(elements)

        return urlList2

    def get_list(self, index, page=''):
        index -= 1
        if index >= len(self.urlList):
            return ['出错了！！']

        try:
            if re.match(r'.*?wiki',self.urlList[index]):
                url = self.urlList[index]
            else:
                url = self.hostUrl + '/' + self.urlList[index]
            if page == '':
                page = requests.get(url, headers=headers, timeout=12).content.decode('utf-8')
            else:
                page = self.Page
        except Exception as e:
            logging.warning('%s' % e)
            return ['悲！服务器驳回了我的此次请求']

        e = etree.HTML(page)
        explain1 = e.xpath('//*[@id="NR-main"]/section/div/div[2]/div/div[2]/div/div//text()')
        if len(explain1) == 0:
            explain1 = e.xpath('//*[@id="NR-main-in"]/section/div/div[2]/div/div[1]/text()')
			
		#测试了好多情况大概就是这些吧……

        explain2 = e.xpath('//*[@id="NR-main"]/section/div/div[2]/div/div[2]/div/ol/li//text()')
        if len(explain2) == 0:
            explain2 = e.xpath('//*[@id="NR-main-in"]/section/div/div[2]/div/ol/li//text()')
            if len(explain2) == 0:
                explain2 = e.xpath('//*[@id="NR-main-in"]/section/div/div[2]/div//text()')
                if len(explain2) == 0:
                    explain2 = e.xpath('//*[@id="NR-main-in"]/section/div/div[2]/div//text()')
                    if len(explain2) == 0:
                        explain2 = e.xpath('//*[@id="mw-content-text"]/div//text()')
                        if len(explain2) == 0:
                            explain2 = e.xpath('//*[@id="mw-content-text"]/div/p[4]//text()')

        syntax = re.compile(r'[\n\t\s]+')
        for elements in explain2:
            elements = re.sub(syntax, '', elements)
            if len(elements) >= 1:
                explain1.append(elements)

        if len(explain1) == 0 and len(explain2) == 0:
            explain1 = []

        self.explaination = explain1

    def get_title_string(self):
        response = ''
        if len(self.titleList) == 0:
            return '未找到搜索结果！', False

        for idx, elements in enumerate(self.titleList):
            response += str(idx + 1) +'、' + elements + '\n'

        return response, True

    def get_explaination(self):
        if len(self.explaination) == 0:
            return self.INFO_NOT_AVAILABLE

        response = ''
        for idx, elements in enumerate(self.explaination):
            if not self.doNewLine and elements[len(elements) - 1:] == '。':
                response += elements.strip() + '\n'
            else:
                response += elements.strip()

            if idx > 60:
                response += ' ...'
                return response

        return response

class Nicowiki:
    def __init__(self, keyWord):
        self.baseUrl = 'https://dic.nicovideo.jp/a/%s' % keyWord
        self.Page = self._getPage()
        self.contentList = self.getContentList()

    def _getPage(self):
        try:
            page = requests.get(self.baseUrl, headers=headers, timeout=10)
        except Exception as e:
            logging.warning('出问题啦！%s' % e)
            return ''
        return page.text

    def getContentList(self):
        e = etree.HTML(self.Page)
        try:
            contentList = e.xpath('//*[@id="article"]/p//text()')
        except Exception as e:
            logging.warning('getContentList wrong %s' % e)
            return []
        return contentList

    def __str__(self):
        if len(self.contentList) == 0:
            return '什么也没查到哦！'

        response = ''
        for elements in self.contentList:
            if elements[len(elements) - 2:] == '。':
                response += elements + '\n'
            else:
                response += elements

        return response


