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
datamap = {
    "tradeId": np.arange(N),
    "pv": 2000000 * (np.random.rand(N) - 0.5),
    "bool": [i % 2 == 0 for i in range(N)],
    "date": [date.today() for i in range(N)],
    "datetime": [datetime.now() for i in range(N)],
    "book": np.random.choice(["CDSBOOK", "EMBOOK", "ALGOBOOK", "IGBOOK", "HYBOOK"], N),
    "MHLLevel6": np.random.choice(["Flow", "Emct", "Structured"], N)
}

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
