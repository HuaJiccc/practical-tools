"""个人工具的内核：纯标准库，不依赖第三方包。

分三层：

* 存数据的：``config`` ``store`` ``notes`` ``picker`` ``todo`` ``currency``
* 干活的：``nlptime`` ``units`` ``languages`` ``translate`` ``aihint``
* 和系统打交道的：``clipboard`` ``notify`` ``network`` ``httpclient``

最上层的 ``api`` 与 ``server`` 把它们拼成一个界面能调的服务。
"""

__all__ = [
    "aihint", "api", "clipboard", "config", "currency", "httpclient", "languages",
    "network", "nlptime", "notes", "notify", "picker", "server", "store", "todo",
    "translate", "units",
]
