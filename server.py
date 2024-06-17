import tornado.websocket
import tornado.web
import tornado.ioloop

from perspective import Table, PerspectiveManager, PerspectiveTornadoHandler
from datetime import date, datetime
import numpy as np
import pandas as pd
import perspective
import pyarrow.feather as feather

print('Starting data generation')
N = 10000
BOOKS = ["CDSBOOK", "EMSOV", "ALGOBOOK", "IGBOOK", "HYBOOK", "EUROCORP"]
HIERARCHY = {
    "CDSBOOK": ["Flow", "NAM IG", "CDS"],
    "EMSOV": ["Emct", "LATAM", "Sov"],
    "ALGOBOOK": ["Flow", "NAM IG", "Algo"],
    "IGBOOK": ["Flow", "NAM IG", "Corp"],
    "HYBOOK": ["Flow", "NAM HY", "Corp"],
    "EUROCORP": ["Flow", "EMEA IG", "Corp"]
}
PRODUCTS = ["Bond", "CDS", "IRS", "Loan"]

datamap = {
    "tradeId": np.arange(N),
    "notional": 2000000 * (np.random.rand(N) - 0.5),
    "pv": 2000000 * (np.random.rand(N) - 0.5),
    "cr01": 2000 * (np.random.rand(N) - 0.5),
    "jumptodefault": 2000000 * (np.random.rand(N) - 0.5),
    "bool": [i % 2 == 0 for i in range(N)],
    "date": [date.today() for i in range(N)],
    "datetime": [datetime.now() for i in range(N)],
    "book": np.random.choice(BOOKS, N),
    "product": np.random.choice(PRODUCTS, N)
}

datamap['hierarchy1'] = [HIERARCHY[b][0] for b in datamap['book']]
datamap['hierarchy2'] = [HIERARCHY[b][1] for b in datamap['book']]
datamap['hierarchy3'] = [HIERARCHY[b][2] for b in datamap['book']]

for i in range(50):
    datamap[f"s{i}"] = [str(j) for j in range(N)]

data = pd.DataFrame(datamap)
print('Finished data generation')

feather.write_feather(data, 'data.lz4.arrow', compression='lz4')
data.to_parquet('data.parquet')

# Create an instance of PerspectiveManager, and host a Table
MANAGER = PerspectiveManager()
print('Creating perspective table')
TABLE = Table(data)

print('Initialized perspective')

# The Table is exposed at `localhost:8888/websocket` with the name `data_source`
MANAGER.host_table("data_source_one", TABLE)

print('Registered table manager')

app = tornado.web.Application([
    # create a websocket endpoint that the client JavaScript can access
    (r"/websocket", PerspectiveTornadoHandler, {"manager": MANAGER, "check_origin": True}),
    (r"/(.*)", tornado.web.StaticFileHandler, {"path":"./", "default_filename":"index.html"}),
])

print('Starting web server')
# Start the Tornado server
app.listen(8888)
loop = tornado.ioloop.IOLoop.current()
loop.start()
