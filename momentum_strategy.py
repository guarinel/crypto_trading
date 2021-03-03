from binance.websockets import BinanceSocketManager
from binance.client import Client
from ta.trend import EMAIndicator as EMA
from binance.enums import *
from credentials import *
import pandas as pd
import numpy as np
import time

class MomentumStrategy:

    def __init__(self):
        self.client = Client(api_key=API_KEY, api_secret=API_SECRET)
        self.bsm_s = BinanceSocketManager(self.client)
        self.bsm_f = BinanceSocketManager(self.client)
        self.symbol = 'BTCUSDT'
        self.bet_size = 0.001
        self.interval = '15m'
        self.data_limit = 200
        self.lim1 = 0.3
        self.lim2 = 0.8
        self.last_signal = 0 
        self.column_names = ['open_time','open','high','low',
                    'close','volume','close_time','quote_asset_volume','number_of_trades',
                    'taker_buy_base_asset_volume','taker_buy_quote_asset_volume','ignore'
                    ]
        self.position_open = False
        self.buy_position = False
        self.sell_position = False
        self.client.futures_change_leverage(symbol = self.symbol, leverage = 10)


        self.conn_key_s = self.bsm_s.start_kline_socket(self.symbol, self.web_socket_handler, interval=self.interval)
        self.bsm_s.start()
        time.sleep(2)
        
    def web_socket_handler(self, data):
        self.is_kline_closed = data['k']['x']
        if self.is_kline_closed:
            self.calculate_signal()
            while self.last_signal == self.signal:
                self.calculate_signal()
            self.last_signal = self.signal
            print(self.signal)
            
            if not self.position_open:
                #open order because kline is closed - runs just the first time 
                if self.signal >= self.lim1 and self.signal <= self.lim2:
                    self.position_open = True
                    self.buy_position = True
                    self.buy_bet_size = self.bet_size
                    self.client.futures_create_order(side='BUY',
                                quantity=self.bet_size,
                                symbol=self.symbol,
                                type='MARKET')

                elif self.signal <= -self.lim1 and self.signal >= -self.lim2:
                    self.position_open = True
                    self.sell_position = True
                    self.sell_bet_size = self.bet_size
                    self.client.futures_create_order(side='SELL',
                                quantity=self.bet_size,
                                symbol=self.symbol,
                                type='MARKET')

            #close positions if were open because kline is closed
            else:
                if self.buy_position:
                    self.position_open = False
                    self.buy_position = False
                    
                    self.client.futures_create_order(side='SELL',
                                quantity=self.buy_bet_size,
                                symbol=self.symbol,
                                type='MARKET')

                if self.sell_position:
                    self.position_open = False
                    self.sell_position = False
                    
                    self.client.futures_create_order(side='BUY',
                                quantity=self.sell_bet_size,
                                symbol=self.symbol,
                                type='MARKET')
                
                #open order because kline is closed
                if self.signal >= self.lim1 and self.signal <= self.lim2:
                    self.position_open = True
                    self.buy_position = True
                    self.buy_bet_size = self.bet_size
                    self.client.futures_create_order(side='BUY',
                                quantity=self.bet_size,
                                symbol=self.symbol,
                                type='MARKET')

                elif self.signal <= -self.lim1 and self.signal >= -self.lim2:
                    self.position_open = True
                    self.sell_position = True
                    self.sell_bet_size = self.bet_size
                    self.client.futures_create_order(side='SELL',
                                quantity=self.bet_size,
                                symbol=self.symbol,
                                type='MARKET')

    def futures_socket(self, data):
        pass
        # self.ask = float(data['data']['a'])
        # self.bid = float(data['data']['b'])
        # self.price = (self.ask + self.bid)/2
        
    def calculate_signal(self):
        df = self.client.futures_klines(symbol=self.symbol, interval=self.interval, limit=self.data_limit)
        
        df = pd.DataFrame(df, columns=self.column_names)
        df['close'] = pd.to_numeric(df['close'])
        nks = [4,8,16]
        nkl = [16,24,32]
        r1 = 12
        r2 = 168
        l = 198
        for i in range(3):
            df[f'ema_s_{i}'] = EMA(df['close'], window=nks[i]).ema_indicator()
            df[f'ema_l_{i}'] = EMA(df['close'], window=nkl[i]).ema_indicator()
            df[f'x{i}'] = df[f'ema_s_{i}'] - df[f'ema_l_{i}']
            df[f'y{i}'] = df[f'x{i}']/np.std(df['close'][l-r1:l])
            df[f'z{i}'] = df[f'y{i}']/np.std(df[f'y{i}'][l-r2:l])
            df[f'u{i}'] = (df[f'z{i}']*np.exp(-(df[f'z{i}']**2)/4)) / (np.sqrt(2)*np.exp(-1/2))
        df['signal'] = (df['u0'] + df['u1'] + df['u2'])/3
        self.signal = df['signal'][l]
    
    def strategy(self):
        pass

if __name__=='__main__':
    m = MomentumStrategy()
