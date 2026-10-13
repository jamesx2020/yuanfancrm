from alembic import context
from app.models import Base
from app import create_app
app=create_app()
with app.extensions['engine'].connect() as connection:
    context.configure(connection=connection,target_metadata=Base.metadata,render_as_batch=True)
    with context.begin_transaction(): context.run_migrations()
