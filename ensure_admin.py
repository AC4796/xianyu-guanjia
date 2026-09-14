"""幂等初始化默认管理员：admin / admin123"""
from db_manager import db_manager

USERNAME = 'admin'
EMAIL = 'admin@localhost.local'
PASSWORD = 'admin123'


def ensure_admin() -> None:
    user = db_manager.get_user_by_username(USERNAME)
    if not user:
        ok = db_manager.create_user(USERNAME, EMAIL, PASSWORD)
        if not ok:
            raise SystemExit('创建 admin 失败')
        print('已创建管理员: admin / admin123')
    else:
        # 保证有可用密码与管理员权限
        db_manager.update_user_password(USERNAME, PASSWORD)
        print('已确保管理员可用: admin / admin123')

    with db_manager.lock:
        cursor = db_manager.conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 1, is_active = 1 WHERE username = ?', (USERNAME,))
        db_manager.conn.commit()

    print('initialized =', db_manager.is_system_initialized())


if __name__ == '__main__':
    ensure_admin()
