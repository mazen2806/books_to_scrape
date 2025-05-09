import aiohttp
import asyncio
from bs4 import BeautifulSoup
from itertools import chain
import re

from db import save_books

PAGES_COUNT = 50
DOMAIN_URL = "https://books.toscrape.com"


def get_books_urls():
    return [f"{DOMAIN_URL}/catalogue/page-{page_number + 1}.html" for page_number in range(PAGES_COUNT)]


async def parse_page(url, target_class):
    """
    Parses page by indicated url
    :param url: page's url
    :param target_class: html element's class
    :return:
    """
    values = []
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            container = soup.find_all("ol", {"class": target_class})

            if len(container) > 0:
                result = container[0].select('li > article')

                for r in result:
                    books_href = r.select('h3 > a')[0].attrs["href"]
                    book_summary = {
                        "name": r.select('h3 > a')[0].attrs["title"],
                        "price": r.select('p.price_color')[0].text,
                        "availability": r.select('p.instock.availability')[0].text.strip(),
                        "books_href": f"{DOMAIN_URL}/catalogue/{books_href}",
                    }
                    values.append(book_summary)

            return values


async def get_quantity_in_stock(book):
    """
    Parses book's details page to get quantity in stock
    :param book: extracted book
    :return:
    """
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get(book["books_href"]) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            container = soup.find("p", {"class": ["instock", "availability"]})
            text = container.text.strip()

            book["quantity_in_stock"] = 0
            del book["books_href"]
            if re.search(r'In stock \((\d+) available\)', text):
                book["quantity_in_stock"] = int(re.search(r'\((\d+)', text).group(1))

            return book


async def get_books():
    """
    Save all books on the pageto mongodb
    :return:
    """
    tasks = []
    books_urls = get_books_urls()

    for book_url in books_urls:
        tasks.append(asyncio.create_task(parse_page(book_url, "row")))

    books = asyncio.gather(*tasks)
    results = await books
    flattened_results = list(chain.from_iterable(results))

    tasks = []
    for item in flattened_results:
        tasks.append(asyncio.create_task(get_quantity_in_stock(item)))

    books_with_quantity = []
    try:
        books_with_quantity = await asyncio.gather(*tasks)
    except asyncio.exceptions.CancelledError as e:
        print(f"CancelledError happened : {e}")
    except aiohttp.client_exceptions.ConnectionTimeoutError as e:
        print(f"ConnectionTimeoutError happened : {e}")
    except aiohttp.client_exceptions.ClientConnectorError as e:
        print(f"ClientConnectorError happened : {e}")
    finally:
        if books_with_quantity:
            save_books(books_with_quantity)

    for task in tasks:
        if task.done() is False:
            task.cancel()
            print(f'Pending: {task.get_name()}')


if __name__ == "__main__":
    print("parsing started")
    asyncio.run(get_books())
    print("parsing finished")
