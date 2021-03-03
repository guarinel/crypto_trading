from python_binance.binance.client import Client
from python_binance.binance.exceptions import BinanceAPIException, BinanceOrderException
from python_binance.binance.websockets import BinanceSocketManager
from twisted.internet import reactor
from credentials import *
from collections import deque
import numpy as np
from pyentrp.entropy import permutation_entropy
import sys
from multiprocessing import Process
import time 
import pandas as pd

class ApiConnection:

    def __init__(self, symbol, quantity):
        self.client = Client(API_KEY, API_SECRET)
    
        self.QUANTITY = float(quantity)
        self.LIM = 0.0015
        self.WINDOW = 1
        self.LENGTH = 5
        self.LAST_INDICATOR = -1
        self.MEAN_SPREAD = deque([], self.LENGTH)
        self.AUX_FUT = []
        self.AUX_SPOT = []
        self.SIGNAL_SELL = False
        self.SIGNAL_BUY = False
        self.POS = 0
        self.I = 0
        self.SYMBOL = symbol
        self.column_names = ['open_time','open','high','low',
                    'close','volume','close_time','quote_asset_volume','number_of_trades',
                    'taker_buy_base_asset_volume','taker_buy_quote_asset_volume','ignore']
        
        self.client.futures_change_leverage(symbol = self.SYMBOL, leverage = 20)
        self._historical_data()

    def open_web_socket(self):
        self.bsm = BinanceSocketManager(self.client)
        self.conn_key_spot = self.bsm.start_kline_socket(self.SYMBOL, self._data_from_spot)
        self.bsm.start()
        
    def open_web_socket_futures(self):
        self.bsm_ = BinanceSocketManager(self.client)
        self.conn_key_fut = self.bsm_.start_futures_kline_socket(self.SYMBOL, self._data_from_futures)
        self.bsm_.start()
        
    def _historical_data(self):
        df_spot = pd.DataFrame(self.client.get_historical_klines(self.SYMBOL, '1m', "6 min ago UTC"), columns=self.column_names)
        df_spot= df_spot[:5]
        df_spot['close'] = pd.to_numeric(df_spot['close'])
        
        df_futures = pd.DataFrame(self.client.futures_klines(symbol=self.SYMBOL, interval='1m', limit=6), columns=self.column_names)
        df_futures = df_futures[:5]
        df_futures['close'] = pd.to_numeric(df_futures['close'])
        df_futures['close_spot'] = df_spot['close']
        df_futures['spread'] = df_futures['close'] / df_futures['close_spot']
        self.MEAN_SPREAD.extend(df_futures['spread'].values)
        time.sleep(5)
  
    def _data_from_futures(self, msg):
        if msg['data']['k']['x']:
            self.close_futures = float(msg['data']['k']['c'])
            self.AUX_FUT.append(self.close_futures)
            if len(self.AUX_FUT) == len(self.AUX_SPOT):
                self.MEAN_SPREAD.append(self.AUX_FUT[-1]/self.AUX_SPOT[-1])
                self.mean = np.mean(self.MEAN_SPREAD)
                self.permutation = self._permutation_entropy()
                self._strategy()
#         else:
#             if self.POS != 0:
#                 if len(self.client.futures_get_open_orders(symbol = self.SYMBOL)) == 1:
#                     self.POS = 0
#                     self.client.futures_cancel_all_open_orders(symbol=self.SYMBOL)
             
    def _data_from_spot(self, msg):
        self.I += 1
        if msg['k']['x']:
            self.close_spot = float(msg['k']['c'])
            self.AUX_SPOT.append(self.close_spot)
            if len(self.AUX_FUT) == len(self.AUX_SPOT):
                self.MEAN_SPREAD.append(self.AUX_FUT[-1]/self.AUX_SPOT[-1])
                self.mean = np.mean(self.MEAN_SPREAD)
                self.permutation = self._permutation_entropy()
                self._strategy()
        else:
            if self.POS != 0:
                if self.I % 100 == 0:
                    if len(self.client.futures_get_open_orders(symbol = self.SYMBOL)) == 1:
                        self.I = 0
                        self.POS = 0
                        self.client.futures_cancel_all_open_orders(symbol=self.SYMBOL)

    def _permutation_entropy(self):
        return permutation_entropy(self.MEAN_SPREAD, order=3, delay=1)
            
    def _strategy(self):
        if self.permutation == 0:
             INDICATOR = (self.close_futures/self.close_spot - self.mean)
        else:
            INDICATOR = (self.close_futures/self.close_spot - self.mean)/ self.permutation

        if INDICATOR > self.LIM:
            self.LAST_INDICATOR = 1
            self.SIGNAL_SELL = True

        elif INDICATOR < - self.LIM:
            self.LAST_INDICATOR = 0
            self.SIGNAL_BUY = True

        if (INDICATOR > -self.LIM) and (INDICATOR < self.LIM):
            if self.LAST_INDICATOR == 1:
                self.LAST_INDICATOR = -1
                self.SIGNAL_BUY = True
                self.SIGNAL_SELL = False

            elif self.LAST_INDICATOR == 0:
                self.LAST_INDICATOR = -1
                self.SIGNAL_SELL = True
                self.SIGNAL_BUY = False

        self._operational()     
        sys.stdout.write(f'\r {INDICATOR}')
        sys.stdout.flush()

    def _operational(self):
     
        if self.POS <= 0:
            if self.SIGNAL_BUY == True:
  #              self.POS += 1
                self._place_orders('BUY', 'SELL')
                self.POS += 1
                print('BUY - BTCUSDTF -- price {} -- '.format(self.close_futures))
                self.SIGNAL_BUY = False

        if self.POS >= 0:
            if self.SIGNAL_SELL == True:
               # self.POS -= 1
                self._place_orders('SELL', 'BUY')
                self.POS -= 1
                print('SELL - BTCUSDTF -- price {} -- '.format(self.close_futures))
                self.SIGNAL_SELL = False
                
    def _place_orders(self, first, second):
        
        self.client.futures_create_order(side=first,
                                quantity=self.QUANTITY,
                                symbol=self.SYMBOL,
                                type='MARKET')
        
        if first == 'BUY':
            stop_loss = round(self.close_futures*0.99,2)
            stop_gain = round(self.close_futures * 1.1, 2)
        else:
            stop_gain = round(self.close_futures * .99, 2)
            stop_loss = round(self.close_futures*1.1, 2)


        self.client.futures_create_order(side=second,
                                   quantity=self.QUANTITY,
                                   type='STOP_MARKET',
                                   symbol=self.SYMBOL,
                                   stopPrice=stop_loss)
        
        self.client.futures_create_order(side=second,
                           quantity=self.QUANTITY,
                           type='TAKE_PROFIT_MARKET',
                           symbol=self.SYMBOL,
                           stopPrice=stop_gain)

        if self.POS == 0:
            self.client.futures_cancel_all_open_orders(symbol=self.SYMBOL)
            
if __name__ == '__main__':
    c = ApiConnection(sys.argv[1], sys.argv[2] )
    p1 = Process(target=c.open_web_socket())
    p1.start()
    p2 = Process(target=c.open_web_socket_futures())
    p2.start()