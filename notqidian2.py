import requests
import shutil
from bs4 import BeautifulSoup
import urllib.request
import shutil
import os
from ebooklib import epub
import time

# http://docs.sourcefabric.org/projects/ebooklib/en/latest/tutorial.html#creating-epub

# mobi格式简介 https://www.cnblogs.com/buptzym/p/5249662.html

UU_URL = "https://www.uukanshu.com/b/69778/"

s = requests.Session()
s.headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}


epubTOC = []
book = epub.EpubBook()

# add copyright description
# copyright = epub.EpubHtml(title="版权声明", file_name="copyright.html")
cpr = epub.EpubHtml(title="Copyright", file_name="copyright.html")
# copyright.content = """<h1>版权声明</h1>
# <p>本工具目的是将免费网络在线小说转换成方便kindle用户阅读的mobi电子书, 作品版权归原作者或网站所有, 请不要将该工具用于非法用途。</p>
# <p>GitHub: https://github.com/fondoger/qidian2mobi</p>
# """
cpr.content = """
<h1>Copyright</h1>

<p>Blah blah blah from a site for epub download, original link https://github.com/fondoger/qidian2mobi
been edited a lot. </p>
"""
book.add_item(cpr)
epubTOC.append(epub.Link("copyright.html", "Copyright", "intro"))


def handle_url(url):
    # handle urls like `//example.com`
    if url[:2] == '//':
        return "http:" + url
    return url

def download_image(url, path):
    url = handle_url(url)
    urllib.request.urlretrieve(url, path)
    print("success saved book cover image:", url)

chapters_count = 0
def handle_chapter(chapter: BeautifulSoup) -> epub.EpubHtml:
    global chapters_count
    # chapter_name = chapter.get_text()
    chapter_name = chapter.find('a').get_text()
    chapter_url = chapter.find('a')['href']
    print(chapters_count, chapter_name, handle_url(chapter_url))
    # r = s.get(handle_url("https://www.uukanshu.com"+chapter_url))
    r = urllib.request.urlopen("https://www.uukanshu.com"+chapter_url).read()
    soup = BeautifulSoup(r.decode("GBK"), features="html.parser")
    # content = soup.find('div', {'class': 'read-content'})
    content = soup.find(id="contentbox").find("div", {"class":"ad-content"})
    chapters_count += 1
    c = epub.EpubHtml(title=chapter_name,
            file_name="chapter_%d.html" % chapters_count)
    c.set_content("<h1>" + chapter_name + "</h1>" + str(content))
    book.add_item(c)
    # time.sleep(0 if random.randint(0, 10) < 8 else 1)
    return c

def handle_list(theList: BeautifulSoup):
    try:
        epc = []
        lastVol = ""
        for item in theList:
            if item.has_attr("class") and item["class"][0] == "volume": # and item.get_text() != lastVol:
                
                if epc:
                    epubTOC.append((epub.Section(lastVol), epc))
                print("handling volume: " + item.get_text())
                lastVol = item.get_text()
                epc = []
            else:
                chap = handle_chapter( item)
                epc.append(chap)
        if epc:
            epubTOC.append((epub.Section(lastVol), epc))
    except KeyboardInterrupt:
        print("finishing")
        if epc:
            epubTOC.append((epub.Section(lastVol), epc))
        
# r = s.get(UU_URL)
r = urllib.request.urlopen("https://www.uukanshu.com/b/69778/").read()
# r.encoding = 'GBK'
soup = BeautifulSoup(r.decode("GBK"), features="html.parser")
book_cover_src = soup.find('a', {'class': 'bookImg'}).find('img')['src']
# print(f"book cover src {book_cover_src}")
book_title = soup.find('a', {'class': 'bookImg'}).find('img')['alt']

print("book cover src", book_cover_src, "book title", book_title)

_jieshao = soup.find_all("dd", {"class":"jieshao_content"})[0]
book_author = _jieshao.find('h2').find("a").get_text()


theList = soup.find(id="chapterList")
# theList.find_all("li")
handle_list(reversed(list(theList.find_all("li"))))


# set title
book.set_title(book_title)
# set author
book.add_author(book_author)
# set cover
download_image(book_cover_src, "book_cover.jpg")
book.set_cover('cover.jpg', open('book_cover.jpg', 'rb').read())
# set book language
book.set_language('zh_Hans')
# set book's TOC
book.toc = epubTOC
# add navigation files
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

# save book
epub.write_epub('book.epub', book)
print(book_title + "-" + book_author, end=" ")
print("successfully saved to book.epub")

print("you can use kindlegen tool to convert epub to mobi")
print("for example: `bin/kindlegen book.epub`")
print("(choose executable file in bin/ directory depending on your operating system.)")
