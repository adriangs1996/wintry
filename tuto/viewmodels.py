from wintry.models import Model


class AllocationsViewModel(Model):
    orderid: str
    sku: str
    batchref: str