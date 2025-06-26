import tornado.websocket
import tornado.web
import tornado.ioloop

from perspective import Table, PerspectiveManager, PerspectiveTornadoHandler
from datetime import date, datetime
import numpy as np
import pandas as pd
import perspective
import pyarrow.feather as feather
import pyarrow as pa
import trino
from trino.auth import BasicAuthentication
import json

print('Starting data generation')
N = 100000
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
# TABLE = Table(data)

print('Initialized perspective')

# The Table is exposed at `localhost:8888/websocket` with the name `data_source`
# MANAGER.host_table("data_source_one", TABLE)

print('Registered table manager')

def convertToRows(cols, tuples):
    rows = []
    for t in tuples:
        row = {}
        for i in range(len(cols)):
            if isinstance(t[i], datetime):
                row[cols[i]] = t[i].isoformat()
            else:
                row[cols[i]] = t[i]
        rows.append(row)
    return rows

class TrinoArrowHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        # Allow CORS if needed
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def options(self):
        # Handle preflight requests
        self.set_status(204)
        self.finish()

    async def post(self):
        try:
            # Parse request body as JSON
            request_data = json.loads(self.request.body)

            # Extract query and connection parameters
            query = request_data.get('query')
            if not query:
                raise ValueError("Missing required 'query' parameter")

            # Optional connection parameters with defaults
            host = request_data.get('host', 'localhost')
            port = request_data.get('port', 8080)
            user = request_data.get('user','admin')
            password = request_data.get('password', None)
            catalog = request_data.get('catalog', 'default')
            schema = request_data.get('schema', 'default')
            format = request_data.get('format', 'arrow')

            print(f"Serving query: {query} from user {user} with format {format}")

            # Connect to Trino
            conn = trino.dbapi.connect(
                host=host,
                port=port,
                user=user,
                auth=BasicAuthentication(user, password) if password and password != "" else None,
                catalog=catalog,
                schema=schema
            )

            if format == 'arrow':
                df = pd.read_sql(query, conn)

                # Convert DataFrame to Arrow Table
                table = pa.Table.from_pandas(df)

                # Serialize to Arrow IPC format
                sink = pa.BufferOutputStream()
                writer = pa.ipc.new_stream(sink, table.schema)
                writer.write_table(table)
                writer.close()
                arrow_bytes = sink.getvalue().to_pybytes()

                # Set appropriate headers and return the Arrow IPC bytes
                self.set_header('Content-Type', 'application/octet-stream')
                self.write(arrow_bytes)
            elif format == 'json':
                cur = conn.cursor()
                cur.execute(query)
                columns = [cd.name for cd in cur.description]
                self.set_header('Content-Type', 'application/json')
                self.write(
                    {
                        "columns": columns,
                        "types": [cd.type_code for cd in cur.description],
                        "query": query,
                        "rows": convertToRows(columns, cur.fetchall()),
                        "error": None,
                        "connectionTested": True
                    }
                )

        except Exception as e:
            print(e)
            self.set_status(500)
            self.write({"error": str(e)})

app = tornado.web.Application([
    # create a websocket endpoint that the client JavaScript can access
    (r"/websocket", PerspectiveTornadoHandler, {"manager": MANAGER, "check_origin": True}),
    (r"/trino", TrinoArrowHandler),
    (r"/(.*)", tornado.web.StaticFileHandler, {"path":"./", "default_filename":"sql2.html"}),
])

print('Starting web server')
# Start the Tornado server
app.listen(8888)
loop = tornado.ioloop.IOLoop.current()
loop.start()
