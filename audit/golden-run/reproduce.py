"""Reproduce the golden run: one real article, full pipeline."""
import sys, time, json
sys.path.insert(0, 'lib')
from thai_factory.fetch.crawl4ai_fetch import crawl, _cache
from thai_factory.extract.dom_cleaner import blockize_from_crawl4ai, CleanedPage
from thai_factory.extract.ai_extractor import extract_observations

def run():
    _cache.clear()
    url = 'https://autolifethailand.tv/wuling-eksion-ev-bev-suv-coming-thailand-28-sep-2026/'
    doc = crawl(url)
    crawl_dict = {'success': True, 'html': doc.raw_html, 'markdown': doc.markdown,
                  'metadata': {'title': doc.title}, 'content_hash': doc.content_hash}
    blocks = blockize_from_crawl4ai(crawl_dict, source_url=url)
    page = CleanedPage(url=url, blocks=blocks, title=doc.title,
                       content_hash=doc.content_hash, fetch_method=doc.fetch_method)
    start = time.time()
    ext = extract_observations(page)
    elapsed = time.time() - start
    ext['total_time_s'] = round(elapsed, 1)
    ext['url'] = url
    ext['content_hash'] = doc.content_hash
    return ext

if __name__ == '__main__':
    result = run()
    print(json.dumps(result, indent=2, ensure_ascii=False))
