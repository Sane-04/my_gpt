# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
from fastapi.testclient import TestClient

from app.main import app


def test_health_check():
    """函数作用：验证 /health 接口返回正常。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "my-gpt-backend"}
