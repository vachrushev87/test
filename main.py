import asyncio
import logging
import os
import sys
# Вот данные штиуки у Вас и без них должно работать у меня на ПК потерял путь по этому дописал костыли
# Получаем абсолютный путь к текущему файлу (main.py). 
current_dir = os.path.dirname(os.path.abspath(__file__))
# Поднимаемся на один уровень вверх, чтобы получить путь к корневой директории проекта
project_root = os.path.abspath(os.path.join(current_dir, '..'))

# Добавляем корневую директорию в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from src.bot import main

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    asyncio.run(main())
