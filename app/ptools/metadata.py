"""影视书籍的元数据抓取已移除（占位模块，保持旧 API 可导入）。"""


class RemovedFeature:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("影视书籍功能已移除")

    def __call__(self, *args, **kwargs):
        raise RuntimeError("影视书籍功能已移除")


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return RemovedFeature
