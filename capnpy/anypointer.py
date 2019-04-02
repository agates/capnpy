from capnpy.blob import Blob
from capnpy import ptr

class AnyPointer(object):

    def __init__(self, struct_, offset):
        self.struct_ = struct_
        self.offset = offset

    def is_struct(self):
        p = self.struct_._read_fast_ptr(self.offset)
        return ptr.kind(p) == ptr.STRUCT

    def is_list(self):
        p = self.struct_._read_fast_ptr(self.offset)
        return ptr.kind(p) == ptr.LIST

    def is_text(self):
        p = self.struct_._read_fast_ptr(self.offset)
        return (ptr.kind(p) == ptr.LIST and
                ptr.list_size_tag(p) == ptr.LIST_SIZE_8)

    def as_text(self):
        return self.struct_._read_str_text(self.offset)

