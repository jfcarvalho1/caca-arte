from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess

class ScoutSpider(Spider):
    name="scout_generic"
    custom_settings={"ROBOTSTXT_OBEY":True,"DOWNLOAD_TIMEOUT":25,"CONCURRENT_REQUESTS_PER_DOMAIN":1,
                     "USER_AGENT":"CacaArteScout/0.1 (+local research)"}
    def __init__(self, urls=None, *args, **kwargs):
        super().__init__(*args,**kwargs); self.start_urls=list(urls or [])
    def start_requests(self):
        for url in self.start_urls: yield Request(url,callback=self.parse)
    def parse(self,response):
        yield {"url":response.url,"status":response.status,"title":response.css("title::text").get(),
               "text":" ".join(response.css("body ::text").getall())[:20000]}

def crawl_urls(urls, output_path):
    """Crawler limitado a URLs fornecidos; respeita robots.txt."""
    process=CrawlerProcess(settings={"FEEDS":{str(output_path):{"format":"json","encoding":"utf8"}},
                                     "LOG_LEVEL":"WARNING"})
    process.crawl(ScoutSpider,urls=urls)
    process.start()
