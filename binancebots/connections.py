'''Module to manage connections to the Binance APIs'''
import asyncio, json, datetime, hashlib, hmac, urllib, httpx, websockets

class ConnectionManager:
	'''Manage connections to the Binance APIs'''
	def __init__(self, base_endpoint: str, ws_uri: str):
		self.base_endpoint = base_endpoint
		self.ws_uri = ws_uri

		self.subscribed_to_ws_stream = False

		self.httpx_client = httpx.AsyncClient()
		self.ws_id = 0
		self.ws_requests = {}
		self.ws_q = asyncio.Queue()

		self.rest_requests = []
		self.rest_request_limits = {} #{'timeperiod': number}

	async def __aenter__(self):
		return self

	async def __aexit__(self, exc_type, exc_value, traceback):
		await self.httpx_client.aclose()
		if self.subscribed_to_ws_stream:
			await self.ws_client.close()
			await self.ws_listener
	


	async def ws_connect(self):
		'''Subscribe to the websocket stream and creates a task to asynchronusly listen to the incoming messages'''
		self.ws_client = await websockets.connect(self.ws_uri, ssl=True)
		self.ws_listener = asyncio.create_task(self.ws_listen())
		self.subscribed_to_ws_stream = True



	async def ws_listen(self):
		'''Listen to incoming ws messages and adds the data to the processing queue'''
		async for message in self.ws_client:
			message = json.loads(message)
			if 'result' in message:
				
				self.ws_requests[message['id']]['response'] = message['result']

			else:
				await self.ws_q.put(message)

	async def ws_send(self, data: dict):
		'''Send data to the websocket server'''
		data['id'] = self.ws_id
		
		self.ws_requests[self.ws_id] = {'data': data, 'response': None}
		await self.ws_client.send(json.dumps(data))
		self.ws_id += 1


	async def close(self):
		'''Close the open connections'''
		await self.httpx_client.aclose()
		if self.subscribed_to_ws_stream:
			self.ws_listener.cancel()
			await self.ws_client.close()


	async def rest_get(self, endpoint: str, **kwargs):
		'''Send a get request to the rest api and returns the response. Raises httpx.HTTPStatusError if the respons status is not 200'''
		params = {} if 'params' not in kwargs else kwargs['params']
		headers = {} if 'headers' not in kwargs else kwargs['headers']
		response =  await self.httpx_client.get(self.base_endpoint + endpoint, headers=headers, params=params) 
		response.raise_for_status()
		return json.loads(response.text)
	

	async def rest_post(self, endpoint: str, **kwargs):	
		'''Send a post request signed using api and secret keys provided, any key errors will raise an httpx.HTTPStatusError exception'''
		params = {} if 'params' not in kwargs else kwargs['params']
		headers = {} if 'headers' not in kwargs else kwargs['headers']
		response =  await self.httpx_client.post(self.base_endpoint + endpoint, params = params, headers = headers)	
		response.raise_for_status()
		return response


	