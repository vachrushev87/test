import os
from logging.config import fileConfig
import sys # Добавьте этот импорт

from sqlalchemy import pool, create_engine, MetaData
from alembic import context
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:mAr84Ina05%25@db:5432/coffeeteam")
print(f"DEBUG: db_url before creation: '{db_url}'")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Добавьте путь к корневой директории проекта в sys.path
# Это гарантирует, что Python найдет ваши модули независимо от того,
# из какой поддиректории запускается Alembic.
# Assumes env.py is in 'migrations' which is one level deep from project root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ИМПОРТИРУЙТЕ Base ИЗ ВАШЕГО МОДУЛЯ database.py
try:
    from src.core.database import Base # Путь должен быть правильным
    target_metadata = Base.metadata
except ImportError as e:
    print(f"ERROR: Could not import Base from src.core.database: {e}")
    # Важно: если импорт не удался, autogenerate не будет работать.
    # Возможно, стоит здесь вызвать SystemExit или поднять исключение.
    target_metadata = None # На случай, если вы хотите, чтобы скрипт продолжал работать без autogenerate

# ... (остальной код env.py) ...
