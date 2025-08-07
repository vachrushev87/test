"""Add UserRole enum type and update users table

Revision ID: 8280618363ca
Revises: 
Create Date: 2025-08-06 09:53:05.874092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8280618363ca'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ПЕРЕМЕЩЕНО СЮДА:
user_role_enum_values = ('admin', 'manager', 'barista', 'pending') # <-- Важно: значения в нижнем регистре
user_role_enum_name = 'user_role'


def upgrade() -> None:
    # 1. Создаем ENUM-тип 'user_role'
    # Используем DDL-инструкции напрямую для Alembic, чтобы создать тип.
    # Добавляем IF NOT EXISTS для устойчивости, хотя Alembic должен это контролировать.
    # Если запустить миграцию на чистую базу, будет создан тип.
    # Если запустить на уже существующую базу (с типом), IF NOT EXISTS предотвратит ошибку.
    quoted_enum_values_sql = ", ".join([f"'{v}'" for v in user_role_enum_values])
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{user_role_enum_name}') THEN
                    CREATE TYPE {user_role_enum_name} AS ENUM ({quoted_enum_values_sql});
                END IF;
            END
            $$;
            """
        )
    )

    # Получаем объект Connection и Inspector для проверки существования столбца
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # Проверяем, существует ли таблица 'users'. Если нет, то нет смысла продолжать.
    # Это важно для миграций с `down_revision = None`. Если вы запускаете на пустой БД,
    # таблицы 'users' может еще не быть.
    if 'users' not in insp.get_table_names():
        print("Таблица 'users' не существует. Пропускаю добавление столбца 'role'.")
        # Возможно, здесь нужно либо пропустить всю оставшуюся часть upgrade,
        # либо создать таблицу 'users' в этой же миграции, если это первая миграция.
        # Для простоты, если tables' не существует, предполагаем, что она будет создана
        # в другой, более ранней миграции, или что текущая миграция не должна быть
        # применена к базе без этой таблицы.
        return # Выходим из upgrade, если таблица users не найдена

    # Проверяем, существует ли столбец 'role' в таблице 'users'
    columns = [col['name'] for col in insp.get_columns('users')]

    if 'role' not in columns:
        # 2. Добавляем столбец `role` в таблицу `users`
        op.add_column(
            'users',
            sa.Column(
                'role',
                # Используем postgresql.ENUM, указывая существующий тип и create_type=False
                # имя типа "user_role" должно соответствовать созданному выше
                postgresql.ENUM(*user_role_enum_values, name=user_role_enum_name, create_type=False),
                nullable=True, # Сначала делаем nullable=True, чтобы обновить старые записи
                server_default=sa.text("'pending'") # Устанавливаем дефолтное значение для НОВЫХ строк
            )
        )

        # 3. Обновляем существующие строки, устанавливая значение по умолчанию 'pending'
        # Это необходимо, чтобы сделать столбец NOT NULL на следующем шаге
        op.execute(
            sa.text("UPDATE users SET role = 'pending' WHERE role IS NULL")
        )

        # 4. Изменяем столбец `role` на `NOT NULL`
        op.alter_column(
            'users',
            'role',
            existing_type=postgresql.ENUM(*user_role_enum_values, name=user_role_enum_name, create_type=False),
            nullable=False,
            existing_server_default=sa.text("'pending'") # Указываем существующий серверный дефолт
        )
    else:
        # Если столбец 'role' уже существует, но миграция запускается повторно
        # (например, после ручных манипуляций или прерванных операций),
        # мы можем попытаться убедиться, что он NOT NULL и имеет правильный тип.
        # Это более сложно, но для простоты, если столбец уже есть, мы предполагаем, что он корректен.
        # Однако, если ENUM-тип отсутствовал, это могло быть причиной первоначальной ошибки.
        # Лучший подход - обеспечить, чтобы ENUM был создан, а затем, если столбец существует,
        # убедиться, что его тип и nullable-свойство соответствуют модели.

        # Проверяем, является ли столбец nullable=True и нужно ли его модифицировать на False
        # Это может быть причиной, если миграция прошла, но alter_column не сработал.
        # Например, если 'role' уже существует, но его тип неверный или он nullable=True,
        # а должен быть nullable=False.

        column_info = next((col for col in insp.get_columns('users') if col['name'] == 'role'), None)
        if column_info and column_info['nullable']:
            print("Столбец 'role' существует, но nullable=True. Изменяем на nullable=False.")
            op.execute(
                sa.text("UPDATE users SET role = 'pending' WHERE role IS NULL")
            )
            op.alter_column(
                'users',
                'role',
                existing_type=postgresql.ENUM(*user_role_enum_values, name=user_role_enum_name, create_type=False),
                nullable=False,
                existing_server_default=sa.text("'pending'")
            )
        elif column_info:
            print("Столбец 'role' уже существует и, предположительно, корректен (nullable=False).")
        else:
            # Это состояние не должно достигаться, так как мы вошли в else,
            # но проверка нужна для полноты.
            print("Неожиданное состояние: столбец 'role' не найден, но код достиг else ветки.")

    # ### end Alembic commands ###


def downgrade() -> None:
    # Define these globally within downgrade as well, or ensure they are truly global
    # If a downgrade script is run independently (e.g., specific downgrade),
    # it might need these definitions to be present.
    # However, since they are defined globally at the module level, this is redundant.
    # Just a note for future refactoring.

    # 1. Сначала делаем столбец `role` nullable, так как могут быть записи, для которых не будет дефолтного значения
    # Но так как мы его сразу DROP, то можно пропустить этот шаг, если нет сложных зависимостей.

    conn = op.get_bind()
    insp = sa.inspect(conn)

    # Проверяем, существует ли таблица 'users' перед попыткой удалить из нее столбец
    if 'users' in insp.get_table_names():
        columns = [col['name'] for col in insp.get_columns('users')]
        if 'role' in columns:
            # 2. Удаляем столбец `role` из таблицы `users`
            # SQLAlchemy автоматически удалит все ограничения, связанные с этим столбцом.
            op.drop_column('users', 'role')
    else:
        print("Таблица 'users' не существует. Пропускаю удаление столбца 'role'.")


    # 3. Удаляем ENUM тип `user_role`
    # Используем DROP TYPE IF EXISTS для безопасности
    op.execute(sa.text(f"DROP TYPE IF EXISTS {user_role_enum_name}"))

    # ### end Alembic commands ###