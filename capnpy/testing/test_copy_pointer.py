import pytest
import struct
from capnpy import ptr
from capnpy.printer import print_buffer

pytest.importorskip('capnpy.copy_pointer')
from capnpy.copy_pointer import MutableBuffer, copy_pointer

class TestMutableBuffer(object):

    def test_allocate(self):
        buf = MutableBuffer(16)
        assert buf.allocate(8) == 0
        s = buf.as_string()
        assert s == '\x00' * 8

    def test_set_int64(self):
        buf = MutableBuffer(8)
        buf.allocate(8)
        buf.set_int64(0, 0x1234ABCD)
        s = buf.as_string()
        assert s == '\xCD\xAB\x34\x12\x00\x00\x00\x00'

    def test_alloc_struct(self):
        buf = MutableBuffer(64)
        buf.allocate(16)
        a = buf.alloc_struct(0, data_size=3, ptrs_size=0)
        b = buf.alloc_struct(8, data_size=1, ptrs_size=0)
        buf.set_int64(a,    1)
        buf.set_int64(a+8,  2)
        buf.set_int64(a+16, 3)
        buf.set_int64(b,    4)
        s = buf.as_string()
        assert s == ('\x04\x00\x00\x00\x03\x00\x00\x00'   # ptr to a (3, 0)
                     '\x0c\x00\x00\x00\x01\x00\x00\x00'   # ptr to b (1, 0)
                     '\x01\x00\x00\x00\x00\x00\x00\x00'   # a: 1
                     '\x02\x00\x00\x00\x00\x00\x00\x00'   #    2
                     '\x03\x00\x00\x00\x00\x00\x00\x00'   #    3
                     '\x04\x00\x00\x00\x00\x00\x00\x00')  # b: 4

    def test_resize(self):
        buf = MutableBuffer()
        buf.allocate(64)
        print
        buf.set_int64(0, 42)
        for i in range(63):
            buf.allocate(64)
        s = buf.as_string()
        assert len(s) == 64*64
        assert s[:8] == struct.pack('q', 42)
        assert s[8:] == '\x00' * (64*64-8)

    def test_resize_big_allocation(self):
        buf = MutableBuffer(32)
        assert buf.length == 32
        assert buf.end == 0
        # make a big allocation, which is bigger than the normal exponential
        # growth of the buffer
        buf.allocate(4096)
        assert buf.length == 4096
        assert buf.end == 4096


class TestCopyPointer(object):

    def copy_struct(self, src, offset, data_size, ptrs_size, bufsize=None):
        if bufsize is None:
            bufsize = len(src)+8
        dst = MutableBuffer(bufsize)
        dst_pos = dst.allocate(8) # allocate the space to store the pointer p
        p = ptr.new_struct(0, data_size, ptrs_size)
        copy_pointer(src, p, offset-8, dst, dst_pos)
        return dst.as_string()

    def test_struct_data(self):
        src = ('garbage0'
               'garbage1'
               '\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
               '\x02\x00\x00\x00\x00\x00\x00\x00') # 2
        dst = self.copy_struct(src, offset=16, data_size=2, ptrs_size=0)
        assert dst == ('\x00\x00\x00\x00\x02\x00\x00\x00'  # ptr (2, 0)
                       '\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                       '\x02\x00\x00\x00\x00\x00\x00\x00') # 2

    def test_struct_ptrs(self):
        ## struct Point {
        ##   x @0 :Int64;
        ##   y @1 :Int64;
        ## }
        ##
        ## struct Rectangle {
        ##   color @0 :Int64;
        ##   a @1 :Point;
        ##   b @2 :Point;
        ## }
        src = ('garbage0'
               '\x01\x00\x00\x00\x00\x00\x00\x00'    # color == 1
               '\x0c\x00\x00\x00\x02\x00\x00\x00'    # ptr to a
               '\x10\x00\x00\x00\x02\x00\x00\x00'    # ptr to b
               'garbage1'
               'garbage2'
               '\x01\x00\x00\x00\x00\x00\x00\x00'    # a.x == 1
               '\x02\x00\x00\x00\x00\x00\x00\x00'    # a.y == 2
               '\x03\x00\x00\x00\x00\x00\x00\x00'    # b.x == 3
               '\x04\x00\x00\x00\x00\x00\x00\x00')   # b.y == 4
        dst = self.copy_struct(src, offset=8, data_size=1, ptrs_size=2)
        assert dst == (
            '\x00\x00\x00\x00\x01\x00\x02\x00'       # ptr to Rectangle (1, 2)
            '\x01\x00\x00\x00\x00\x00\x00\x00'       # color == 1
            '\x04\x00\x00\x00\x02\x00\x00\x00'       # ptr to a
            '\x08\x00\x00\x00\x02\x00\x00\x00'       # ptr to b
            '\x01\x00\x00\x00\x00\x00\x00\x00'       # a.x == 1
            '\x02\x00\x00\x00\x00\x00\x00\x00'       # a.y == 2
            '\x03\x00\x00\x00\x00\x00\x00\x00'       # b.x == 3
            '\x04\x00\x00\x00\x00\x00\x00\x00')      # b.y == 4

    def test_struct_out_of_bound(self):
        ## struct Point {
        ##   x @0 :Int64;
        ##   y @1 :Int64;
        ## }
        ##
        ## struct Rectangle {
        ##   color @0 :Int64;
        ##   a @1 :Point;
        ##   b @2 :Point;
        ## }
        src = (
            '\x01\x00\x00\x00\x00\x00\x00\x00'       # color == 1
            '\x04\x00\x00\x00\x02\x00\x00\x00'       # ptr to a
            '\x08\x00\x00\x00\x02\x00\x00\x00'       # ptr to b
            '\x01\x00\x00\x00\x00\x00\x00\x00'       # a.x == 1
            '\x02\x00\x00\x00\x00\x00\x00\x00'       # a.y == 2
            '\x03\x00\x00\x00\x00\x00\x00\x00'       # b.x == 3
            '\x04\x00\x00\x00\x00\x00\x00\x00')      # b.y == 4
        #
        # sanity check: make sure that src is a valid message
        dst = self.copy_struct(src, offset=0, data_size=1, ptrs_size=2)
        assert dst[8:] == src # dst contain an extra pointer to the content of src
        #
        cut_data = src[:-8] # remove b.y, to trigger an out-of-bound in the data section
        with pytest.raises(IndexError) as exc:
            self.copy_struct(cut_data, offset=0, data_size=1, ptrs_size=2,
                             bufsize=128)
        assert exc.value.message.startswith('Invalid capnproto message: offset out of bound')
        #
        cut_ptr = src[:8] # remove from "ptr to a" to the end, to trigger an
                           # out-of-bound in the ptrs section
        with pytest.raises(IndexError) as exc:
            self.copy_struct(cut_ptr, offset=0, data_size=1, ptrs_size=2,
                             bufsize=128)
        assert exc.value.message.startswith('Invalid capnproto message: offset out of bound')

    def test_struct_one_null_ptr(self):
        src = (
            '\x01\x00\x00\x00\x00\x00\x00\x00'    # color == 1
            '\x0c\x00\x00\x00\x02\x00\x00\x00'    # ptr to a
            '\x00\x00\x00\x00\x00\x00\x00\x00'    # ptr to b, NULL
            'garbage1'
            'garbage2'
            '\x01\x00\x00\x00\x00\x00\x00\x00'    # a.x == 1
            '\x02\x00\x00\x00\x00\x00\x00\x00')   # a.y == 2
        dst = self.copy_struct(src, offset=0, data_size=1, ptrs_size=2)
        assert dst == (
            '\x00\x00\x00\x00\x01\x00\x02\x00'    # ptr to Rectangle (1, 2)
            '\x01\x00\x00\x00\x00\x00\x00\x00'    # color == 1
            '\x04\x00\x00\x00\x02\x00\x00\x00'    # ptr to a
            '\x00\x00\x00\x00\x00\x00\x00\x00'    # ptr to b, NULL
            '\x01\x00\x00\x00\x00\x00\x00\x00'    # a.x == 1
            '\x02\x00\x00\x00\x00\x00\x00\x00')   # a.y == 2

    def test_struct_all_null_ptrs(self):
        src = (
            '\x01\x00\x00\x00\x00\x00\x00\x00'    # color == 1
            '\x00\x00\x00\x00\x00\x00\x00\x00'    # ptr to a, NULL
            '\x00\x00\x00\x00\x00\x00\x00\x00')   # ptr to b, NULL
        dst = self.copy_struct(src, offset=0, data_size=1, ptrs_size=2)
        assert dst == (
            '\x00\x00\x00\x00\x01\x00\x02\x00' +    # ptr to Rectangle (1, 2)
            src)

    def test_list_primitive(self):
        src = (
            '\x11\x00\x00\x00\x1a\x00\x00\x00'   #  0: ptr list<8>  to a
            '\x15\x00\x00\x00\x1b\x00\x00\x00'   #  8: ptr list<16> to b
            '\x19\x00\x00\x00\x1c\x00\x00\x00'   # 16: ptr list<32> to c
            '\x21\x00\x00\x00\x1d\x00\x00\x00'   # 24: ptr list<64> to d
            'garbage1'
            '\x01\x02\x03\x00\x00\x00\x00\x00'   # 40: a = [1, 2, 3]
            'garbage2'
            '\x04\x00\x05\x00\x06\x00\x00\x00'   # 56: b = [4, 5, 6]
            'garbage3'
            '\x07\x00\x00\x00\x08\x00\x00\x00'   # 72: c = [7, 8,
            '\x09\x00\x00\x00\x00\x00\x00\x00'   # 80:      9]
            'garbage4'
            '\x0a\x00\x00\x00\x00\x00\x00\x00'   # 96: d = [10,
            '\x0b\x00\x00\x00\x00\x00\x00\x00'   # 104      11,
            '\x0c\x00\x00\x00\x00\x00\x00\x00')  # 112      12]
        dst = self.copy_struct(src, offset=0, data_size=0, ptrs_size=4)
        assert dst == (
            '\x00\x00\x00\x00\x00\x00\x04\x00'   # ptr to Rectangle (0, 4)
            '\x0d\x00\x00\x00\x1a\x00\x00\x00'   #  0: ptr list<8>  to a
            '\x0d\x00\x00\x00\x1b\x00\x00\x00'   #  8: ptr list<16> to b
            '\x0d\x00\x00\x00\x1c\x00\x00\x00'   # 16: ptr list<32> to c
            '\x11\x00\x00\x00\x1d\x00\x00\x00'   # 24: ptr list<64> to d
            '\x01\x02\x03\x00\x00\x00\x00\x00'   # 32: a = [1, 2, 3]
            '\x04\x00\x05\x00\x06\x00\x00\x00'   # 40: b = [4, 5, 6]
            '\x07\x00\x00\x00\x08\x00\x00\x00'   # 48: c = [7, 8, 9]
            '\x09\x00\x00\x00\x00\x00\x00\x00'   # 56:
            '\x0a\x00\x00\x00\x00\x00\x00\x00'   # 64: d = [10, 11, 12]
            '\x0b\x00\x00\x00\x00\x00\x00\x00'   # 72
            '\x0c\x00\x00\x00\x00\x00\x00\x00')  # 80

    def test_list_of_bool(self):
        src = (
            '\x05\x00\x00\x00\x19\x00\x00\x00'    # ptrlist
            'garbage1'
            '\x03\x00\x00\x00\x00\x00\x00\x00')   # [True, True, False]
        dst = self.copy_struct(src, offset=0, data_size=0, ptrs_size=1)
        assert dst == (
            '\x00\x00\x00\x00\x00\x00\x01\x00'    # ptr (0, 1)
            '\x01\x00\x00\x00\x19\x00\x00\x00'    # ptrlist
            '\x03\x00\x00\x00\x00\x00\x00\x00')   # [True, True, False]

    def test_list_of_pointers(self):
        src = (
            '\x01\x00\x00\x00\x1e\x00\x00\x00'   # ptr to list of strings
            '\x0d\x00\x00\x00\x32\x00\x00\x00'   # strings[0] == ptr to #0
            '\x11\x00\x00\x00\x52\x00\x00\x00'   # strings[1] == ptr to #1
            '\x19\x00\x00\x00\xb2\x00\x00\x00'   # strings[2] == ptr to #2
            'garbage1'
            'h' 'e' 'l' 'l' 'o' '\x00\x00\x00'   # #0
            'garbage2'
            'c' 'a' 'p' 'n' 'p' 'r' 'o' 't'      # #1...
            'o' '\x00\x00\x00\x00\x00\x00\x00'
            'garbage3'
            't' 'h' 'i' 's' ' ' 'i' 's' ' '      # #2...
            'a' ' ' 'l' 'o' 'n' 'g' ' ' 's'
            't' 'r' 'i' 'n' 'g' '\x00\x00\x00')
        dst = self.copy_struct(src, offset=0, data_size=0, ptrs_size=1)
        assert dst == (
            '\x00\x00\x00\x00\x00\x00\x01\x00'   # ptr (0, 1)
            '\x01\x00\x00\x00\x1e\x00\x00\x00'   # ptr to list of strings
            '\x09\x00\x00\x00\x32\x00\x00\x00'   # strings[0] == ptr to #0
            '\x09\x00\x00\x00\x52\x00\x00\x00'   # strings[1] == ptr to #1
            '\x0d\x00\x00\x00\xb2\x00\x00\x00'   # strings[2] == ptr to #2
            'h' 'e' 'l' 'l' 'o' '\x00\x00\x00'   # #0
            'c' 'a' 'p' 'n' 'p' 'r' 'o' 't'      # #1...
            'o' '\x00\x00\x00\x00\x00\x00\x00'
            't' 'h' 'i' 's' ' ' 'i' 's' ' '      # #2...
            'a' ' ' 'l' 'o' 'n' 'g' ' ' 's'
            't' 'r' 'i' 'n' 'g' '\x00\x00\x00')

    def test_list_of_pointers_all_null(self):
        src = ('\x01\x00\x00\x00\x1e\x00\x00\x00'   # ptr to list
               '\x00\x00\x00\x00\x00\x00\x00\x00'
               '\x00\x00\x00\x00\x00\x00\x00\x00'
               '\x00\x00\x00\x00\x00\x00\x00\x00'
               'garbage1')
        dst = self.copy_struct(src, offset=0, data_size=0, ptrs_size=1)
        assert dst == (
            '\x00\x00\x00\x00\x00\x00\x01\x00'   # ptr (0, 1)
            '\x01\x00\x00\x00\x1e\x00\x00\x00'   # ptr to list
            '\x00\x00\x00\x00\x00\x00\x00\x00'
            '\x00\x00\x00\x00\x00\x00\x00\x00'
            '\x00\x00\x00\x00\x00\x00\x00\x00')

    def test_list_composite(self):
        ## struct Point {
        ##   x @0 :Int64;
        ##   y @1 :Int64;
        ##   name @2 :Text;
        ## }
        src = (
            '\x05\x00\x00\x00\x4f\x00\x00\x00'   # ptr to list
            'garbage1'
            '\x0c\x00\x00\x00\x02\x00\x01\x00'   # list tag
            '\x01\x00\x00\x00\x00\x00\x00\x00'   # points[0].x == 1
            '\x02\x00\x00\x00\x00\x00\x00\x00'   # points[0].y == 2
            '\x1d\x00\x00\x00\x42\x00\x00\x00'   # points[0].name == ptr
            '\x03\x00\x00\x00\x00\x00\x00\x00'   # points[1].x == 3
            '\x04\x00\x00\x00\x00\x00\x00\x00'   # points[1].y == 4
            '\x19\x00\x00\x00\x42\x00\x00\x00'   # points[1].name == ptr
            '\x05\x00\x00\x00\x00\x00\x00\x00'   # points[2].x == 5
            '\x06\x00\x00\x00\x00\x00\x00\x00'   # points[2].y == 6
            '\x15\x00\x00\x00\x42\x00\x00\x00'   # points[2].name == ptr
            'garbage2'
            'P' 'o' 'i' 'n' 't' ' ' 'A' '\x00'
            'garbage3'
            'P' 'o' 'i' 'n' 't' ' ' 'B' '\x00'
            'garbage4'
            'P' 'o' 'i' 'n' 't' ' ' 'C' '\x00')
        dst = self.copy_struct(src, offset=0, data_size=0, ptrs_size=1)
        assert dst == (
            '\x00\x00\x00\x00\x00\x00\x01\x00'   # ptr (0, 1)
            '\x01\x00\x00\x00\x4f\x00\x00\x00'   # ptr to list
            '\x0c\x00\x00\x00\x02\x00\x01\x00'   # list tag
            '\x01\x00\x00\x00\x00\x00\x00\x00'   # points[0].x == 1
            '\x02\x00\x00\x00\x00\x00\x00\x00'   # points[0].y == 2
            '\x19\x00\x00\x00\x42\x00\x00\x00'   # points[0].name == ptr
            '\x03\x00\x00\x00\x00\x00\x00\x00'   # points[1].x == 3
            '\x04\x00\x00\x00\x00\x00\x00\x00'   # points[1].y == 4
            '\x11\x00\x00\x00\x42\x00\x00\x00'   # points[1].name == ptr
            '\x05\x00\x00\x00\x00\x00\x00\x00'   # points[2].x == 5
            '\x06\x00\x00\x00\x00\x00\x00\x00'   # points[2].y == 6
            '\x09\x00\x00\x00\x42\x00\x00\x00'   # points[2].name == ptr
            'P' 'o' 'i' 'n' 't' ' ' 'A' '\x00'
            'P' 'o' 'i' 'n' 't' ' ' 'B' '\x00'
            'P' 'o' 'i' 'n' 't' ' ' 'C' '\x00')

    def test_list_composite_out_of_bound(self):
        ## struct Point {
        ##   x @0 :Int64;
        ##   y @1 :Int64;
        ##   name @2 :Text;
        ## }
        src = (
            '\x05\x00\x00\x00\x4f\x00\x00\x00'   # ptr to list
            'garbage1'
            '\x0c\x00\x00\x00\x02\x00\x01\x00'   # list tag
            '\x01\x00\x00\x00\x00\x00\x00\x00'   # points[0].x == 1
            '\x02\x00\x00\x00\x00\x00\x00\x00'   # points[0].y == 2
            '\x1d\x00\x00\x00\x42\x00\x00\x00'   # points[0].name == ptr
            '\x03\x00\x00\x00\x00\x00\x00\x00'   # points[1].x == 3
            '\x04\x00\x00\x00\x00\x00\x00\x00'   # points[1].y == 4
            '\x19\x00\x00\x00\x42\x00\x00\x00'   # points[1].name == ptr
            '\x05\x00\x00\x00\x00\x00\x00\x00'   # points[2].x == 5
            '\x06\x00\x00\x00\x00\x00\x00\x00')  # points[2].y == 6
                                                 # points[2].name MISSING
        with pytest.raises(IndexError) as exc:
            self.copy_struct(src, offset=0, data_size=0, ptrs_size=1, bufsize=128)
        assert exc.value.message == ('Invalid capnproto message: '
                                     'offset out of bound at position 16 (96 > 88)')
