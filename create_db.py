import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv
import os

load_dotenv()

# Your Neon database URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Parse the database URL
parsed_url = urlparse(DATABASE_URL)

# Connect to the database
conn = psycopg2.connect(
    dbname=parsed_url.path[1:],
    user=parsed_url.username,
    password=parsed_url.password,
    host=parsed_url.hostname,
    port=parsed_url.port
)

# Create a cursor object
cursor = conn.cursor()

# Create the table
create_table_query = '''
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    signal_type VARCHAR(20),
    symbol VARCHAR(50),
    timeframe VARCHAR(20),
    entry_price FLOAT,
    tp FLOAT,
    sl FLOAT,
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
'''

cursor.execute(create_table_query)

# Commit the changes
conn.commit()

# Close the cursor and connection
cursor.close()
conn.close()
