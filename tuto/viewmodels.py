from wintry.generators import AutoString
from wintry.models import Id, Model


class AllocationsViewModel(Model):
    id: str = Id(default_factory=AutoString)
    orderid: str
    sku: str
    batchref: str