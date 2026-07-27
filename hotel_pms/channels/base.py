from __future__ import annotations
from abc import ABC,abstractmethod
_REGISTRY={}
class ChannelAdapter(ABC):
 @abstractmethod
 def push_inventory(self,property,start_date,end_date):...
 @abstractmethod
 def push_rates(self,property,start_date,end_date):...
 @abstractmethod
 def pull_reservations(self,property,since=None):...
def register_adapter(name,adapter_cls):_REGISTRY[name]=adapter_cls
def get_adapter(name,**kwargs):
 if name not in _REGISTRY:raise KeyError(f'Unknown channel adapter: {name}')
 return _REGISTRY[name](**kwargs)
