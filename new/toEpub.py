import sys
import argparse
from bs4 import BeautifulSoup
import urllib.request
from urllib.request import Request
from ebooklib import epub

#region parser

parser = argparse.ArgumentParser(description="To Epub Parser",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-s", "--source", action="store",
                    help="Source to read from (uu: UU看书; 51: 无忧书城)",
                    default="uu")
parser.add_argument("-v", "--verbose", action="store_true", help="Run in verbose mode")
parser.add_argument("link", type=str, help="Link of book chapter listing")
parser.add_argument("uid", type=str, help="Unique identifier of ebook")

#endregion


class EpubMaker:
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    
    def __init__(self, link, encoding:str, verbose) -> None:
        self.book = epub.EpubBook()
        self.tableOfContents = []
        self.link = link
        self.sectionBuffer = []
        self.currentSectionTitle = ""
        self.chapterCount = 0
        self.encoding:str = encoding
        
        self.verbose = verbose
        
    def downloadImage(self, imgLink:str, path:str):
        if self.verbose: print(f"getting image {imgLink}")
        
        if imgLink[:2] == '//':
            imgLink = "http:" + imgLink
        
        req = Request(url=imgLink, headers=self.headers)
        i = urllib.request.urlopen(req)
        with open(path, "wb") as im:
            im.write(i.read())
        
        
        if self.verbose: print(f"Successfully retrieved img {imgLink}")
        
    def _initBook(self, identifier:str, title:str, author:str, cover:str, lang:str="zh-Hans", desc:str=""):
        """
        NOTE: cover must be a full link: e.g. https://www.hetushu.com + the image link
        """
        self.book.set_identifier(identifier)
        self.book.set_title(title)
        self.book.set_language(lang)
        self.book.add_author(author)
        self.book.add_metadata("DC", "description", desc)
        # image stuff
        self.downloadImage(cover, "bookCover.jpg")
        with open("bookCover.jpg", "rb") as i:
            self.book.set_cover("cover.jpg", i.read())
        
        self.lang = lang
        self.title = title
        
        # add preface stuff
        preface = epub.EpubHtml(title="序言", file_name="preface.html", lang=self.lang)
        
        preface.content = """
        <h1>序言</h1>
        
        <p>
        This epub was automatically created by a parsing script. 
        It is based off a script from https://github.com/fondoger/qidian2mobi, which didn't
        really work.
        </p>
        
        <p>
        The contents belong to whichever entity has copyright over the book - legally I should 
        say that you should not use this to pirate. It is here for "educational purposes" only.
        </p>
        
        <p>
        This script is provided as-is and without warranty. You are responsible if you get into 
        trouble using it.
        It is given under the CC ShareAlike 4.0 license (CC BY-SA 4.0)
        
        </p> 
        <p>
        (c) 2022 Adrakaris.
        </p>
        """
        
        self.book.add_item(preface)
        self.tableOfContents.append(preface)
        
        self.book.spine = ["nav", preface]
        
    def _makeSection(self, sectionName):
        # self._endSection()
        # secChap = epub.EpubHtml(title=sectionName, file_name=f"{sectionName}.html", lang=self.lang)
        # secChap.content = f"<h1>{sectionName}</h1>"
        # self.book.add_item(secChap)
        
        self.currentSectionTitle = sectionName
        self.sectionBuffer = []
    
    def _endSection(self):
        self.tableOfContents.append((epub.Section(self.currentSectionTitle), [i for i in self.sectionBuffer]))
        
    def _finishBook(self):
        
        
        self.book.toc = self.tableOfContents
        
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())
        
        if self.verbose:
            print("toc", self.book.toc)
            print("cs", self.currentSectionTitle)
        
        epub.write_epub(self.title + ".epub", self.book)
        print("Done.")


class UUKanShu(EpubMaker):
    def __init__(self, link, uid, encoding:str="GBK", verbose=False) -> None:
        super().__init__(link, encoding, verbose)
        
        # get site
        # nicely, uukanshu doesn't forbid urlllib
        r = urllib.request.urlopen(link).read()
        # replace errors
        mainSoup = BeautifulSoup(r.decode(self.encoding), features="html.parser")
        
        # get titles and descriptions
        # img and title
        jieshaoImg = mainSoup.find("dt", {"class": "jieshao-img"})
        if verbose: print(jieshaoImg)
        image = jieshaoImg.find("a").find("img") # type:ignore
        imageSrc:str = image["src"] # type:ignore
        title:str = image["alt"] # type:ignore
        # author and description
        jieshaoContent = mainSoup.find("dd", {"class":"jieshao_content"})
        if verbose: print(jieshaoContent)
        authorName = jieshaoContent.find("h2").find("a").get_text() # type:ignore
        desc = jieshaoContent.find("h3").get_text() # type:ignore
        # dbg
        if self.verbose: print(f"Found {title} by {authorName}, desc\n{desc}")
        
        # init book
        self._initBook(uid, title, authorName, imageSrc, desc=desc)
        
        # send list off to process 
        self._parseList(reversed(list(mainSoup.find(id="chapterList").find_all("li")))) # type:ignore
        
        # finish book
        self._finishBook()

    def _parseList(self, listOfItems):
        try:
            
            for item in listOfItems:
                if self.verbose: print(item)
                # li class volume is volume header
                if item.has_attr("class") and item["class"][0] == "volume":
                    if self.currentSectionTitle != "":
                        self._endSection()
                    print(f"Section {item.get_text()}")
                    self._makeSection(item.get_text())
                else:
                    link = item.find("a")
                    chapName = link.get_text()
                    chapLink = link["href"]
                    self._handleChapter(chapLink, chapName)
        except KeyboardInterrupt:
            print("finishing early")
        except UnicodeDecodeError as e:
            # NOTE: UUKanshu is formatted weird, that may lead to such errors happening in some books.
            print("Found unicode decode error, ending early since otherwise you'll just have empty pages:")
            print(e)
        finally:
            self._endSection()
            
    def _handleChapter(self, chapLink, chapName):
        # a specific chapter
        print(f"> {self.chapterCount} {chapName} ({chapLink})")
        
        r = urllib.request.urlopen("https://www.uukanshu.com" + chapLink).read()
        soup = BeautifulSoup(r.decode(self.encoding), features="html.parser")
        
        title = soup.find(id="timu").get_text() # type:ignore
        # content = soup.find(id="contentbox").find_all("p", recursive=False).get_text("\n\n") # type:ignore
        content = soup.find(id="contentbox")
        for c in content.findChildren(recursive=False):
            if c.name != "p":
                c.extract()
        content = content.get_text("\n\n")
        
        if self.verbose: 
            print("========CONTENT===========")
            print(content) #.split("\n\n"))
            print("=======/CONTENT===========")
        
        # content = map(str, content)
        # content = "\n".join(content)
        content = "\n".join(list(map(lambda x: "<p>" + x + "</p>", content.split("\n\n"))))
        
        # if self.verbose: 
        #     print("========CONTENT=2=========")
        #     print(content) #.split("\n\n"))
        #     print("=======/CONTENT=2=========")
        
        self.chapterCount += 1
        
        chap = epub.EpubHtml(uid=title,
                             title=title,
                             file_name=f"chap-{self.chapterCount}.html",
                             lang=self.lang)
        chap.content = f"<h2>{self.currentSectionTitle}・{title}</h2>" + content
        
        self.book.add_item(chap)
        self.sectionBuffer.append(chap)
        self.book.spine.append(chap)


class WuYouShuCheng(EpubMaker):
    def __init__(self, link:str, uid:str, encoding:str="utf-8", verbose:bool=False) -> None:
        super().__init__(link, encoding, verbose)
        
        # get site
        r = Request(link, headers=EpubMaker.headers)
        r = urllib.request.urlopen(r).read()
        mainSoup = BeautifulSoup(r.decode(self.encoding), features="html.parser")
        
        # image - 51shucheng has no images
        imageLink = "https://www.51shucheng.net/images/logo.png"
        
        catalog = mainSoup.find("div", {"class":"catalog"})
        # title
        title = catalog.find("h1").get_text()  # type:ignore
        # author
        author = catalog.find("div", {"class":"info"}).get_text().split("作者：")[1]  # type:ignore        
        # desc
        description = catalog.find("div", {"class":"intro"}).get_text()  # type:ignore
        
        if self.verbose: print(f"Found {title} by {author}, desc\n{description}")
        
        # initi book
        self._initBook(uid, title, author, imageLink, desc=description)
        
        # send off to process
        self._parseList(mainSoup.find("div", {"class":"mulu-list"}).ul.findChildren(recursive=False))
        
        # finish book
        self._finishBook()
        
    def _parseList(self, listOfItems):
        try:
            for item in listOfItems:
                if self.verbose: print(item)
                # 51shucheng seems not to do volumes
                chapName = item.a.get_text()
                chapLink = item.a["href"]
                self._handleChapter(chapLink, chapName)
        
        except KeyboardInterrupt:
            print("finishing early")
            
    def _handleChapter(self, chapLink, chapName):
        print(f"> {self.chapterCount} {chapName} ({chapLink})")
        
        r = Request(chapLink, headers=EpubMaker.headers)
        r = urllib.request.urlopen(r).read()
        soup = BeautifulSoup(r.decode(self.encoding), features="html.parser")
        
        title = soup.find("h1").get_text()
        
        content = soup.find(id="neirong")
        
        if self.verbose: 
            print("========CONTENT===========")
            print(content) #.split("\n\n"))
            print("=======/CONTENT===========")
            
        self.chapterCount += 1
        
        chap = epub.EpubHtml(uid=title,
                             title=title,
                             file_name=f"chap-{self.chapterCount}.html",
                             lang=self.lang)
        chap.content = f"<h2>{title}</h2>" + str(content)
        
        self.book.add_item(chap)
        self.tableOfContents.append(chap)
        self.book.spine.append(chap)
    
    
    

if __name__ == "__main__":
    args = parser.parse_args()
    if args.source == "uu":
        UUKanShu(args.link, args.uid, verbose=args.verbose)
    elif args.source == "51":
        WuYouShuCheng(args.link, args.uid, verbose=args.verbose)
    else:
        print("Error: no compatible sourec found")
        exit(1)