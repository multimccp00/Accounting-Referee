import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pymysql
from config.db_connection import DB_CONFIG

try:
    conn = pymysql.connect(host=DB_CONFIG['host'], port=DB_CONFIG['port'],
                           user=DB_CONFIG['user'], password=DB_CONFIG['password'],
                           db=DB_CONFIG['dbname'], connect_timeout=5)
    cur = conn.cursor()
    cur.execute('SELECT season, COUNT(*) FROM games GROUP BY season')
    print('seasons', cur.fetchall())
    cur.execute('SELECT COUNT(*) FROM games')
    print('total rows', cur.fetchone())
    conn.close()
except Exception as e:
    print('error', e)
