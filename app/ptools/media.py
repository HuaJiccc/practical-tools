"""影视书籍功能已移除。

这个占位模块只用于让旧的 API 代码保持可导入；任何真正调用都会立刻报错，
确保「影视书籍」不会再以任何形式出现在程序里。
"""


class RemovedFeature:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("影视书籍功能已移除")

    def __call__(self, *args, **kwargs):
        raise RuntimeError("影视书籍功能已移除")


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return RemovedFeature
