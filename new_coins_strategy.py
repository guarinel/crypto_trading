import time 
import pandas as pd
from python_binance.binance.client import Client
from credentials import *


if __name__ == '__main__':
    
    while True:
        boolean = False
        signal = False
        new_request = []
        vector_of_new_pairs = []
        vector_of_coins  = []
        trades  = []                

        client = Client(API_KEY, API_SECRET)

        with open('symbols.txt', 'r') as f:
            vector = [line.strip() for line in f]

        for key in client.get_exchange_info()['symbols']:
            new_request.append(key['symbol'])

        for value in new_request:
            if value not in vector:
                for cryptocoin in ["BUSD", "BTC", "ETH", "USDT"]:
                    if cryptocoin in value:
                        vector_of_new_pairs += [[value.split(cryptocoin)[0], cryptocoin]]
                        boolean = True
        if boolean:
            for value in vector:
                for new_pair in vector_of_new_pairs:
                    if new_pair[0] not in value:
                        trades.append(new_pair[0] + new_pair[1])
                        trades_to_perform = set(trades)
                        signal = True

        if signal:
            for pair in trades_to_perform:
                if 'USD' in pair:
                    price = float(client.get_symbol_ticker(symbol=pair)['price'])
                    quantity = round(13/price, 2)
                if 'ETH' in pair:
                    price_dol = float(client.get_symbol_ticker(symbol='ETHUSDT')['price'])
                    value = 13/price_dol
                    price_symbol = float(client.get_symbol_ticker(symbol=pair)['price'])
                    quantity = round(value/price_symbol,2)
                if 'BTC' in pair:
                    price_dol = float(client.get_symbol_ticker(symbol='BTCUSDT')['price'])
                    value = 13/price_dol
                    price_symbol = float(client.get_symbol_ticker(symbol=pair)['price'])
                    quantity = round(value/price_symbol,2)
                    
                client.create_order(side='BUY',
                                        quantity=quantity,
                                        symbol=pair,
                                        type='MARKET')
                print(f'COMPRADO {pair}')


        with open('symbols.txt', 'w') as f:
            for item in new_request:
                f.write("%s\n" % item)

        print('-----RUN----- {}'.format(pd.Timestamp.now()))
        time.sleep(300)