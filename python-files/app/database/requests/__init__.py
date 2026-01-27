"""
Пакет для работы с базой данных.

Содержит функции для работы с пользователями, странами, админами и наказаниями.
"""

# Пользователи (users)
from .users import (
    get_or_create_user,
    get_full_user_profile,
    get_user_by_username,
    reset_user_cooldown,
    get_top_ludomans
)

# Стран функции (countries)
from .countries import (
    create_meme_country,
    assign_ruler,
    get_country_by_name,
    find_country_by_fuzzy_name,
    get_my_country_stats,
    join_country,
    leave_country,
    transfer_ruler,
    delete_country,
    set_position,
    kick_user,
    set_tax_rate,
    collect_taxes,
    get_all_countries,
    get_global_stats,
    donate_to_country_treasury,
    edit_country_name,
    edit_country_ideology,
    edit_country_description,
    edit_country_map_url,
    edit_country_flag,
    edit_country_memename,
    edit_country_url,
    get_country_by_ruler_id
    
)

# Админы и наказания (admins)
from .admins import (
    add_admin,
    give_points,
    get_current_user_admin_level,
    add_punishment,
    remove_punishment,
    is_punished,
    get_active_punishments,
    get_all_active_punishments_by_type
)

# Отзывы и рейтинги (reviews)
from .reviews import (
    REVIEW_COOLDOWN_DAYS,
    check_review_cooldown,
    save_review,
    get_countries_for_list,
    get_top_users,
    get_history
)

# Особые утилиты (utils)
from .utils import (
    has_active_country_ban,
    check_creation_allowed,
    get_creation_status,
    get_user_country
)
