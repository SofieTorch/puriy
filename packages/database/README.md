# Database package

During development, to squash all the migrations into a single clean migration:

```bash
# 1. Drop all tables and the alembic version table
# (make sure there is not any active connection)
cd packages/database
alembic downgrade base

# 2. Delete all migration files
rm alembic/versions/*.py

# 3. Autogenerate a fresh single migration from current models
alembic revision --autogenerate -m "initial"
```

Before applying migrations, the generated migration needs to import sqlmodel
and add the PostGIS extension to the schema, also make sure that the types
are removed in the downgrade, so add the following lines:

```python
import sqlmodel

...

def upgrade() -> None:
    # Ensure PostGIS extension is available
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    ...

def downgrade() -> None:
    # Add at the end of everything
    op.execute('DROP TYPE IF EXISTS linestatus')
    op.execute('DROP TYPE IF EXISTS estimationstatus')
    op.execute('DROP TYPE IF EXISTS sessionstatus')
    op.execute('DROP TYPE IF EXISTS processingstatus')
    op.execute('DROP TYPE IF EXISTS segmentstatus')
    op.execute('DROP TYPE IF EXISTS tripstatus')
    op.execute('DROP TYPE IF EXISTS votechoice')
```

Now we can apply our brand-new migration:

```
# 4. Apply it
alembic upgrade head
```