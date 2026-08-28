import os


# 自动化测试不调用真实模型或网络服务，避免消耗额度并保持结果可重复。
os.environ["JUDGE_MODEL_PROVIDER"] = "mock"
os.environ["COMPOSE_MODEL_PROVIDER"] = "mock"
os.environ["KNOWLEDGE_PROVIDER"] = "mock"
os.environ["NETWORK_SEARCH_ENABLED"] = "false"
os.environ["NETWORK_SEARCH_PROVIDER"] = "mock"
