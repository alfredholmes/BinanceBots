import asyncio
import json
import datetime

import hashlib, hmac, urllib
import httpx

from binancebots.orderbooks import OrderBookManager



class SpotAccount:
	def __init__(self, api, secret, order_book_manager=None, endpoint='https://api.binance.com/api/v3/'):
		self.httpx_client = httpx.AsyncClient()
		self.api_key = api
		self.secret_key = secret
		if order_book_manager is not None:
			self.order_book_manager = order_book_manager
			self.own_orderbook = False
		else:
			self.orderbook_manager = OrderBookManager()
			self.own_orderbook = True
		
		self.endpoint = endpoint
		self.exchange_data = None
		self.market_filters = {}

		self.default_base_asset = 'BNB'
		self.backup_base_asset = 'BTC'

		self.spot_balances = None


	#close the connection
	async def close(self):
		await self.httpx_client.aclose()
		if self.own_orderbook:
			await self.orderbook_manager.close_connection()
	

	async def get_account_data(self):
		if self.exchange_data is None:
			await self.get_exchange_data()

		await self.get_account_balance()



	async def get_exchange_data(self):
		response = await self.httpx_client.get(self.endpoint + 'exchangeInfo')
		self.exchange_data = json.loads(response.text)
		

		#the following code is perhaps inefficient as it loops through the symbols quite a lot
		#get a list of all the currencies
		base_assets = set(symbol['baseAsset'] for symbol in self.exchange_data['symbols'])
		quote_assets = set(symbol['quoteAsset'] for symbol in self.exchange_data['symbols'])
		
		self.tradable_assets = base_assets.union(quote_assets)

		

		for symbol_data in self.exchange_data['symbols']:
			
			symbol = symbol_data['symbol']
			self.market_filters[symbol] = {'precision': int(symbol_data['baseAssetPrecision']), 'precision_quote': int(symbol_data['quoteAssetPrecision'])}
			for f in symbol_data['filters']:
				if f['filterType'] == 'LOT_SIZE':
					self.market_filters[symbol]['min_order'] = float(f['minQty'])
					self.market_filters[symbol]['max_order'] = float(f['maxQty'])
					self.market_filters[symbol]['step_size'] = float(f['stepSize'])
				elif f['filterType'] == 'MIN_NOTIONAL':
					self.market_filters[symbol]['min_order_quote'] = float(f['minNotional'])
	

	async def track_orderbooks(self, *symbols):
		await self.orderbook_manager.subscribe_to_depths(*(symbol for symbol in symbols))


	async def weighted_portfolio(symbols=None, base='BTC'):
		#currently assyming everything has a btc market
		#if the symbols is None then we will just get the whole portfolio
		#get account data if we need to
		if self.spot_balances is None:
			self.get_account_balance()

		#if no symbols were passed then just get the whole portfolio weighted
		if symbols is None:

			if len(self.spot_balances) == 1:
				return {self.spot_balances.keys()[0]: 1.0}

			untracked = []
			for currency in self.spot_balances:
				if currency + base in self.market_filters:
					if (currency + base).lower() not in self.orderbook_manager.subscriptions:
						untracked.append((currency + base).lower())
				elif (base + currency).lower() in self.market_filters:
					if (base + currency).lower() not in self.orderbook_manager.subscriptions:
						untracked.append((base + currency).lower())

			await self.track_orderbooks(*(symbol for symbol in untracked))

			weighted = {}

			for currency, balance in self.spot_balances.items():
				if currency == base:
					weighted[currency] = balance
				if currency + base in self.market_filters:
					weighted[currency] = balance * self.orderbook_manager.market_price()
				elif base + currency in self.market_filters:
					#
		else:
			pass



	#Trade Methods
	#buy volume worth of to_buy with to_sell
	async def limit_buy(self, to_buy, to_sell, volume):
		pass

	
	async def market_buy(self, to_buy, to_sell, volume):
		if to_buy + to_sell in self.market_filters:
			pass
		elif to_sell + to_buy in self.market_filters:
			pass

	#sell volume worth of to_sell to to_buy
	async def limit_sell(self, to_sell, to_buy, volume):
		pass

	async def market_sell(self, to_sell, to_buy, volume):
		pass

	async def get_account_balance(self):
		params = self.sign_params()
		headers = {'X-MBX-APIKEY': self.api_key}

		response = await self.httpx_client.get(self.endpoint + 'account', headers=headers, params=params)
		account = json.loads(response.text)

		self.spot_balances = {asset['asset']: float(asset['free']) for asset in account['balances'] if float(asset['free']) != 0}


	def sign_params(self, params={}):
		ts = int(datetime.datetime.now().timestamp() * 1000)
		params['timestamp'] = str(ts)
		params['signature'] = self.generate_signature(params)

		return params


	def generate_signature(self, params):
		return hmac.new(self.secret_key.encode('utf-8'), urllib.parse.urlencode(params).encode('utf-8'), hashlib.sha256).hexdigest()		