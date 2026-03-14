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
and add the PostGIS extension to the schema, so add the following lines:

```python
import sqlmodel

...

def upgrade() -> None:
    # Ensure PostGIS extension is available
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    ...
```

Now we can apply our brand-new migration:

```
# 4. Apply it
alembic upgrade head
```