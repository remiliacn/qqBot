import os
import random
import re
import time

import requests

#临时图库，在网站不可用的时候使用里面的图片。
#github : remiliacn

INFO_NOT_AVAILABLE = "信息暂不可用"
headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"
}

class ShadiaoAPI:
    def __init__(self):
        self.base_dir = 'E:/biaoqing/'
        if not os.path.exists(self.base_dir):
            try:
                os.makedirs(self.base_dir)
            except IOError:
                raise IOError(f'Unable to create directory: {self.base_dir}')

        random.seed(time.time_ns())
        self.page = random.randint(0, 10)
        self.base_url = f"https://www.fabiaoqing.com/biaoqing/lists/page/{self.page}.html"
        self.image_list = self.get_image_list()

    def get_image_list(self):
        try:
            page = requests.get(self.base_url, timeout=15)
        except Exception as e:
            print("发表情网不可用：错误%s" % e)
            imageList = os.listdir(self.base_dir)
            return imageList

        imageList = re.findall(r'data-original="(.*?)"', page.text)
        return imageList

    def get_picture(self, download_count=1):
        random.seed(time.time_ns())
        image_list = self.image_list

        file_list = []

        for count in range(download_count):
            image = random.choice(image_list)
            try:
                file_detailed_name = image.split('/')[-1]
                file_name = self.base_dir + file_detailed_name
                if not os.path.exists(file_name):
                    img = requests.get(image, timeout=6)
                    img.raise_for_status()
                    with open(file_name, 'wb') as f:
                        f.write(img.content)

                print("Picture got:", file_name)
                if download_count > 1:
                    file_list.append(file_name)

                return file_name

            except Exception as e:
                image_list = os.listdir(self.base_dir)
                print("Exception occurred: %s" % e)
                if download_count == 1:
                    return self.base_dir + random.choice(image_list)

        return file_list if file_list else []


class Avalidator:
    def __init__(self, text):
        self.base_url = f'https://www.libredmm.com/movies/{text}'
        self.torrent_url = 'https://idope.se/'
        self.page_text, = self._get_page_text()
        self.product_number = text

    def _get_page_text(self) -> str:
        try:
            page = requests.get(self.base_url, timeout=15)
        except Exception as e:
            print("Timetout when fetching data %s" % e)
            return ''
            
        if page.status_code == 200:
            return page.text

        return ''

    def get_content(self) -> str:
        from lxml import etree
        if self.page_text:
            e = etree.HTML(self.page_text)
            title_temp = e.xpath('/html/body/main/h1/span[2]/text()')[0]
            if not title_temp:
                title = '暂不可用'
            else:
                title = ''.join(title_temp)

            date = re.findall(r'<dd>(\d+.*?)</dd>', self.page_text)
            date = date[0] if date else '暂不可用'

            source = re.findall(r'<dd><a href="(.*?)"', self.page_text)
            if not source:
                source = '暂不可用'
            else:
                source = str(source[0]).replace('http://', '').replace('https://', '').replace('.', '点')

            torrentURL = self.torrent_url + f'/torrent-list/{self.product_number}'
            try:
                page = requests.get(torrentURL, timeout=10)
            except Exception as e:
                return f'连接出错: {e}'
                
            urls = re.findall('<a href="(/torrent/.*?)"', page.text)
            if not urls:
                tor = '暂不可用'
            else:
                try:
                    page = requests.get(self.torrent_url + urls[0], timeout=10)
                except Exception as err:
                    return f'连接出错 {err}'
                    
                tor = re.findall(r'<div id="deteails">(.*?)</div>', page.text)
                if not tor:
                    tor = '暂不可用'
                else:
                    tor = tor[0]

            return f'从番号{self.product_number}我拿到了以下结果：\n' \
                   f'片名：{title}\n' \
                   f'日期：{date}\n' \
                   f'来源：{source}\n' \
                   f'磁链：{tor}'

        return f'未查到与番号"{self.product_number}"相关的内容。'

