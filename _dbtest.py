import sys
sys.path.insert(0, ".")
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('db_connection', 'db_connection.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
cfg = mod.DB_CONFIG
print("host:", cfg.get('host'), "db:", cfg.get('dbname'))

import pymysql
try:
    conn = pymysql.connect(host=cfg['host'], port=int(cfg.get('port',3306)),
                           user=cfg['user'], password=cfg.get('password',''),
                           db=cfg['dbname'], connect_timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM games")
    print("CONNECTED. games rows:", cur.fetchone()[0])
    cur.execute("SELECT DISTINCT season FROM games")
    print("seasons:", [r[0] for r in cur.fetchall()])
    cur.close(); conn.close()
    print("DB_OK")
except Exception as e:
    print("DB_FAIL:", e)
