from flask import g, current_app
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

def init_db(app):
    engine=create_engine('sqlite:///'+app.config['DATABASE_PATH'],connect_args={'timeout':20})
    @event.listens_for(engine,'connect')
    def pragma(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA busy_timeout=20000')
    app.extensions['engine']=engine
    @app.teardown_appcontext
    def close(_):
        if 'db' in g: g.db.rollback(); g.db.close()
def db():
    if 'db' not in g: g.db=Session(current_app.extensions['engine'],expire_on_commit=False)
    return g.db
