from alembic import context
from sqlalchemy import create_engine, event

from app.db import db_path

engine = create_engine(f"sqlite:///{db_path()}")


# pysqlite 는 DDL 앞에서 트랜잭션을 열지 않는다. 직접 BEGIN 해야 이전이 "한 번에 끝나거나
# 아무것도 바뀌지 않는" 상태가 된다. (DATA-MIGRATION-PLAN 5단계)
@event.listens_for(engine, "connect")
def _autocommit_mode(dbapi_conn, _record):
    dbapi_conn.isolation_level = None


@event.listens_for(engine, "begin")
def _begin(conn):
    conn.exec_driver_sql("BEGIN")


with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=None,
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()
