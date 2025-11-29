from enum import Enum

TK_SHIFT_MASK    = 0x0001
TK_CONTROL_MASK  = 0x0004

class source_properties(Enum):
    normal = 0
    read_only = 1
