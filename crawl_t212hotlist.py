from time import sleep, gmtime
from datetime import datetime
import pytz
from pprint import pprint

from pymongo import MongoClient

from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

from config import get_client

driver = None


def init_driver():
    global driver
    driver = webdriver.Chrome(ChromeDriverManager().install())


def crawl_list():
    # variables for log
    log = {
        '_id': datetime.utcnow(),
        'info': [],
        'leaderboard': {
            'crawled_tickers': 0,
            'crawled_owners': 0
        },
        'risers': {
            'crawled_tickers': 0,
            'crawled_starts': 0,
            'crawled_ends': 0
        },
        'fallers': {
            'crawled_tickers': 0,
            'crawled_starts': 0,
            'crawled_ends': 0
        }
    }

    client = get_client()
    sleep_multiplierer = 2

    driver.get('https://www.trading212.com/en/hotlist')
    sleep(2*sleep_multiplierer)
    
    try:
        driver.find_element_by_xpath('/html/body/div[1]/section[1]/div/div/a').click()
    except:
        log['info'].append('Cookie information could not be clicked')

    sleep(1*sleep_multiplierer)
    timestamp = datetime.utcnow()
    try:
        # before: Last updated: 09/02/2021, 20:40:16. Info based on Trading 212's investing accounts data.
        timestamp = str_to_date(driver.find_element_by_xpath('/html/body/div[1]/section[2]/div/div/div[2]/div[3]').get_attribute('innerHTML').replace('Last updated: ', '').replace('/', '-').replace(',', '').replace('. Info based on Trading 212\'s investing accounts data.', ''))
    except:
        log['info'].append('timestamp could not be crawled')
    # if already crawled for this timestamp
    if client.signals.t212_hotlist.count_documents({'_id': timestamp}) > 0:
        log['info'].append('Already crawled')
        return

    # get leaderboard
    data = {'_id': timestamp, 'leaderboard': []}
    for i in range(1, 100+1):
        ticker = 'N/A'
        try:
            ticker = driver.find_element_by_xpath('/html/body/div[1]/section[2]/div/div/div[2]/div[2]/div[' + str(i) + ']/div[2]/div/div/div').get_attribute('innerHTML')
            log['leaderboard']['crawled_tickers'] += 1
        except:
            log['info'].append('ticker ' + str(i) + ' could not be crawled')

        owners = 0
        try:
            owners = int(driver.find_element_by_xpath('/html/body/div[1]/section[2]/div/div/div[2]/div[2]/div[' + str(i) + ']/div[4]/div').get_attribute('innerHTML').replace(',', ''))
            log['leaderboard']['crawled_owners'] += 1
        except:
            log['info'].append('owners ' + str(i) + ' could not be crawled')
        
        data['leaderboard'].append({'ticker': ticker, 'owners': owners})

    # get risers/fallers
    data['risers'] = {}
    data['fallers'] = {}
    timeframes = ['1H', '4H', '8H', '1D', '7D', '30D']

    for n in range(1, 2+1):
        direction = 'risers' if n == 1 else 'fallers'
        try:
            driver.find_element_by_xpath('/html/body/div[1]/section[2]/div/div/div[1]/div/div[' + str(int(1 + n)) + ']').click()
        except:
            log['info'].append('could not switch to hotlisttab to ' + direction)
        sleep(1*sleep_multiplierer)
        for i in range(1, 6+1):
            timeframe = timeframes[i-1]
            try:
                driver.find_element_by_xpath('/html/body/div[1]/section[2]/div/div/div[2]/div[2]/div[' + str(i) + ']').click()
            except:
                log['info'].append('could not switch timeframetab to ' + timeframe)
            
            sleep(3*sleep_multiplierer)

            try:
                data[direction][timeframe] = []
                for j in range(1, 100+1):
                    ticker = driver.find_element_by_xpath('/html/body/div[1]/section[2]/div/div/div[2]/div[4]/div[' + str(j) + ']/div[2]/div/div/div').get_attribute('innerHTML')
                    log[direction]['crawled_tickers'] += 1
                    start = int(driver.find_element_by_xpath('/html/body/div[1]/section[2]/div/div/div[2]/div[4]/div[' + str(j) + ']/div[5]').get_attribute('innerHTML').replace(',', ''))
                    log[direction]['crawled_starts'] += 1
                    end = int(driver.find_element_by_xpath('/html/body/div[1]/section[2]/div/div/div[2]/div[4]/div[' + str(j) + ']/div[6]').get_attribute('innerHTML').replace(',', ''))
                    log[direction]['crawled_ends'] += 1
                    if start == 0 and i < 5:
                        print('IPO', timeframe, direction, ticker)
                        try:
                            client.org.markets.insert_many([{'_id': ticker, 'IPO': datetime.combine(datetime.utcnow().date(), datetime.min.time())}], ordered=False)
                        except:
                            pass
                    data[direction][timeframe].append({'ticker': ticker, 'start': start, 'end': end})
            except:
                pass

    client.signals.t212_hotlist.insert_one(data)
    client.logs.t212_hotlist.insert_one(log)


def str_to_date(str):
    date = datetime.strptime(str, '%d-%m-%Y %H:%M:%S')
    date_eastern = pytz.timezone('Europe/Berlin').localize(date)
    return date_eastern.astimezone(pytz.utc)
