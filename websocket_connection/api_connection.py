from python_binance.binance.client import Client
from python_binance.binance.exceptions import BinanceAPIException, BinanceOrderException
from python_binance.binance.websockets import BinanceSocketManager
from twisted.internet import reactor
from credentials import *
from collections import deque
import numpy as np
from pyentrp.entropy import permutation_entropy
import sys

class ApiConnection:

    def __init__(self):
        self.client = Client(API_KEY, API_SECRET)
       
        self.QUANTITY = 0.005
        self.LIM = 0.0007
        self.WINDOW = 100
        self.LENGTH = 3000
        self.LAST_INDICATOR = -1
        self.VECTOR = deque([], self.LENGTH)
        self.MEAN_SPREAD = deque([], self.LENGTH)
        self.AUX = []
        self.AUX_SPREAD = []
        self.SIGNAL_SELL = False
        self.SIGNAL_BUY = False
        self.value_spot = 47600
        self.value_future = 47600
        self.POS = 0
        self.SYMBOL = 'BTCUSDT'
        self.client.futures_change_leverage(symbol = self.SYMBOL, leverage = 10)

    def open_web_socket(self):
        self.bsm = BinanceSocketManager(self.client)
        self.conn_key_fut = self.bsm.start_multiplex_socket_futures(['btcusdt@bookTicker'], self._data_from_futures)
        
        self.conn_key_spot = self.bsm.start_multiplex_socket(['btcusdt@bookTicker'], self._data_from_spot)

        self.bsm.start()

    def _data_from_futures(self, msg):
        self.ask = float(msg['data']['a'])
        self.bid = float(msg['data']['b'])
        self.value_future = (self.ask + self.bid) / 2.0

        if len(self.VECTOR) < self.LENGTH:
            self.VECTOR.append(self.value_future)
            self.MEAN_SPREAD.append(self.value_future/self.value_spot)
            if len(self.MEAN_SPREAD) == 2998:
                self.mean = np.mean(self.MEAN_SPREAD)
                self.permutation = self._permutation_entropy()
        else:
            self.AUX_SPREAD.append(self.value_future/self.value_spot)
            self.AUX.append(self.value_future)
            if len(self.AUX) == self.WINDOW:
                self.VECTOR.extend(self.AUX)
                self.MEAN_SPREAD.extend(self.AUX_SPREAD)
                
                self.mean = np.mean(self.MEAN_SPREAD)
                self.permutation = self._permutation_entropy()
                
                self.AUX = []
                self.AUX_SPREAD = []
            self._strategy()
              
    def _data_from_spot(self, msg):
        self.value_spot =  (float(msg['data']['b']) + float(msg['data']['a'])) / 2.0

        if len(self.VECTOR) < self.LENGTH:
            self.VECTOR.append(self.value_spot)
            self.MEAN_SPREAD.append(self.value_future/self.value_spot)
            if len(self.MEAN_SPREAD) == 2998:
                self.mean = np.mean(self.MEAN_SPREAD)
                self.permutation = self._permutation_entropy()
        else:
            self.AUX_SPREAD.append(self.value_future/self.value_spot)
            self.AUX.append(self.value_spot)
            if len(self.AUX) == self.WINDOW:
                self.VECTOR.extend(self.AUX)
                self.MEAN_SPREAD.extend(self.AUX_SPREAD)
                
                self.mean = np.mean(self.MEAN_SPREAD)
                self.permutation = self._permutation_entropy()
                
                self.AUX = []
                self.AUX_SPREAD = []
            self._strategy()

    def _permutation_entropy(self):
        return permutation_entropy(self.MEAN_SPREAD, order=5, delay=1)
            
    def _strategy(self):
        INDICATOR = (self.value_future/self.value_spot - self.mean)/ self.permutation

        if INDICATOR > self.LIM:
            self.LAST_INDICATOR = 1
            self.SIGNAL_SELL = True

        elif INDICATOR < - self.LIM:
            self.LAST_INDICATOR = 0
            self.SIGNAL_BUY = True

        if (INDICATOR > -0.00007) and (INDICATOR < 0.00007):
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
                self.POS += 1
                self._place_orders('BUY', 'SELL')
                print('BUY - BTCUSDTF -- price {} -- '.format(self.ask))
                self.SIGNAL_BUY = False

        if self.POS >= 0:
            if self.SIGNAL_SELL == True:
                self.POS -= 1
                self._place_orders('SELL', 'BUY')
                print('SELL - BTCUSDTF -- price {} -- '.format(self.bid))
                self.SIGNAL_SELL = False
                
    def _place_orders(self, first, second):

        self.client.futures_create_order(side=first,
                                quantity=self.QUANTITY,
                                symbol=self.SYMBOL,
                                type='MARKET')
        
        if first == 'BUY':
            stop_loss = round(self.bid*0.99,2)
            stop_gain = round(self.bid * 1.01, 2)
        else:
            stop_gain = round(self.ask * .99, 2)
            stop_loss = round(self.ask*1.01, 2)

        
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
            
#         if len(self.client.get_open_orders(symbol = self.SYMBOL)) == 1:
#             self.POS = 0
#             self.client.futures_cancel_all_open_orders(symbol=self.SYMBOL)

if __name__ == '__main__':
    c = ApiConnection()
    c.open_web_socket()



    #####KRAKEN
    ##API_KEY = daFyg8Kn4rD1LPZXmZ+J4I+10JwUBVDdx8ktdSFhi1CV6is7kNYcqlt+
    # SECRET_KEY = nFJW2PeKIcYFXlzaiJQe3lgOkeI3Q9OsQFF/xVRQA4Uz4G+Br/9E0LF9MSawYlejTtBt+gp7q0IEI+fKg/sYLQ==