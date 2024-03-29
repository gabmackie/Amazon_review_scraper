# -*- coding: utf-8 -*-
"""
Created on Sun Sep 26 16:15:01 2021

@author: gabri
"""
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re


def build_review_url(url):  # Turn a regular review into a product review
    # Replace default page with product reviews
    review_url = url.replace('dp', 'product-reviews')

    # Strip everything off the review before a particular expression, and then add on a different ending
    review_url = re.split('/ref=', review_url)[0] + \
        '/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews&pageNumber='

    return review_url


def request_url(url, no_tries=0):
    if no_tries == 3:
        print('URL request has failed 3 times. Moving to next URL')
        return 'NA', 3

    try:
        # Having a header helps convince Amazon that we're not a bot
        headers = ({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0',
                    'Accept-Language': 'en-US, en;q=0.5'})

        # Make the request, timeout means it throw an error if it takes longer than 1 sec
        time.sleep(2)
        r = requests.get(url=url, headers=headers, timeout=1)

        r.raise_for_status()

        # Create a soup object, lxml is a fast and lenient HTML parser
        soup = BeautifulSoup(r.text, "lxml")

        return soup, no_tries

    # This handles all types of error in the requests package
    except requests.exceptions.RequestException as err:
        print('An error has occured when trying to reach the url')
        print(err)
        no_tries += 1
        request_url(url, no_tries)


def get_reviews(soup, page):
    # Find all the reviews, identified by their particular tag
    reviews = soup.find_all('div', {'data-hook': 'review'})
    print(f"{len(reviews)} reviews found on this page")

    for item in reviews:
        # Throwing this in a try statement lets us skip reviews that break our code
        # The key example of these would be reviews in foreign languages
        try:
            # Take the product's title from the overall object
            product = soup.title.text.replace(
                'Amazon.co.uk:Customer reviews:', '').strip()

            # Extract each object by identifying it's tags
            title = item.find('a', {'data-hook': 'review-title'}).text.strip()
            rating = float(item.find('i', {
                           'data-hook': 'review-star-rating'}).text.replace(' out of 5 stars', '').strip())
            body = item.find('span', {'data-hook': 'review-body'}).text.strip()

            # Date requires slightly more processing, it returns a longer string of text
            # We can't use replace because that text can change based on country
            date = item.find('span', {'data-hook': 'review-date'}).text.strip()

            # Use regular expressions to extract the date
            date = re.search('[0-9].*$', date).group(0)
            # Convert it to a date type using pandas
            date = pd.to_datetime(date).date()

            # Helpfulness also requires more work
            try:
                # First, extract the text and strip it
                helpfulness = item.find(
                    'span', {'data-hook': 'helpful-vote-statement'}).text.strip()

                # If 1 person found it helpful, that's written as 'One'
                # So we'll search that using regex
                if re.match('One', helpfulness):
                    helpfulness = 1

                # If multiple people found it helpful, that's given as a digit
                else:
                    # Remove the unnecessary text and convert to an integer
                    helpfulness = int(helpfulness.replace(
                        ' people found this helpful', ''))

            # If no one found it helpful, then running the above code throws an error
            except AttributeError:
                helpfulness = 0

            review = {'product': product, 'title': title, 'page': page, 'rating': rating, 'helpfulness': helpfulness,
                      'date': date, 'body': body}

            review_list.append(review)

        # If we can't run our extraction code, just go to the next review
        except:
            print("Skipping a review due to try/except failure")
            reviews_skipped.append(item)
            pass


def scrape_pages(input_url, max_pages):
    pages_skipped = 0
    reviews_initial = len(review_list)
    reviews_skipped_initial = len(reviews_skipped)

    # This runs through the x pages of reviews
    for x in range(1, max_pages):
        # Set the input url to the correct page number
        current_url = f'{input_url}{x}'

        soup, no_tries = request_url(current_url)

        if no_tries == 3:
            pages_skipped += 1
            continue

        # TODO: Only use this if something is wrong
        # print(soup.body)

        get_reviews(soup, x)

        if x == 1:
            global_ratings_text = soup.find(
                'div', {'data-hook': 'cr-filter-info-review-rating-count'})

            numbers = re.findall('[0-9]+', global_ratings_text.text)

            global_ratings = int(numbers[0])
            global_reviews = int(numbers[1])

        if global_reviews == 0:
            break

        # Print to give feedback on the progress
        print(f'Getting page: {x}')
        print(len(review_list))

        # This tag is found when the "next page" option is unavailable
        # When that's the case we want to end our search
        if soup.find('li', {'class': 'a-disabled a-last'}):
            print('Final page found')
            break

    reviews_final = len(review_list)
    num_reviews_current = reviews_final - reviews_initial

    reviews_skipped_final = len(reviews_skipped)
    num_skipped_current = reviews_skipped_final - reviews_skipped_initial

    new_data = {'global_ratings': global_ratings,
                'global_reviews': global_reviews, 'errors_encountered': no_tries, 'pages_skipped': pages_skipped,
                'reviews_scraped': num_reviews_current, 'reviews_skipped': num_skipped_current}
    additional_product_data.append(new_data)
    print(new_data)


review_list = []
output_url = 'product_reviews.xlsx'
reviews_skipped = []
additional_product_data = []

# Get urls from a url spreadsheet, and run through each of them
products_df = pd.read_excel('product_urls.xlsx', header=0,
                            index_col=0)

product_urls = products_df['url'].values.tolist()

for product_url in product_urls:
    review_url = build_review_url(product_url)

    print(f'Scraping url {review_url}')

    scrape_pages(review_url, 10)

# Convert our list to a df and save it to an excel file
df = pd.DataFrame(review_list)
df.to_excel(output_url, index=False)
print("Data saved")

print(f'The total of skipped reviews was {len(reviews_skipped)}')
