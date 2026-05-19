# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import uuid

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_does_not_store_plaintext():
    """函数作用：验证密码哈希不会保存明文且可正确校验。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    password = "safe-password"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_can_be_decoded_to_user_id():
    """函数作用：验证 JWT 能携带并还原用户 UUID。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    token, expires_at = create_access_token(user_id)

    assert token
    assert expires_at.isoformat()
    assert decode_access_token(token) == user_id
