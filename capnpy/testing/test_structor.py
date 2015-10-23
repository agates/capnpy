import py
from pypytools.codegen import Code
from capnpy.struct_ import Struct
from capnpy.structor import Structor
from capnpy.schema import Field, Type

class TestComputeFormat(object):

    def test_compute_format_simple(self):
        fields = [Field.new_slot('x', 0, Type.new_int64()),
                  Field.new_slot('y', 1, Type.new_int64())]
        s = Structor(None, 'fake', data_size=2, ptrs_size=0, fields=fields)
        assert s.fmt == 'qq'

    def test_compute_format_holes(self):
        fields = [Field.new_slot('x', 0, Type.new_int32()),
                  Field.new_slot('y', 1, Type.new_int64())]
        s = Structor(None, 'fake', data_size=2, ptrs_size=0, fields=fields)
        assert s.fmt == 'ixxxxq'


def new_structor(**kwds):
    class Namespace:
        from capnpy.builder import StructBuilder

    code = Code()
    code['__'] = Namespace
    structor = Structor(None, 'ctor', **kwds)
    structor.declare(code)
    code.compile()
    static_ctor = code['ctor']
    # the structor is defined as @staticmethod, so before calling we need to
    # manually __get__ it
    return static_ctor.__get__(object)




def test_unsupported(monkeypatch):
    monkeypatch.setattr(Structor, '_unsupported', 'fake')
    ctor = new_structor(data_size=0, ptrs_size=0, fields=[])
    exc = py.test.raises(NotImplementedError, "ctor()")
    assert exc.value.message == 'fake'

def test_primitive():
    fields = [Field.new_slot('x', 0, Type.new_int64()),
              Field.new_slot('y', 1, Type.new_int64())]
    ctor = new_structor(data_size=2, ptrs_size=0, fields=fields)
    buf = ctor(1, 2)
    assert buf == ('\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                   '\x02\x00\x00\x00\x00\x00\x00\x00') # 2

def test_argnames():
    fields = [Field.new_slot('x', 0, Type.new_int64()),
              Field.new_slot('y', 1, Type.new_int64())]
    ctor = new_structor(data_size=2, ptrs_size=0, fields=fields)
    buf = ctor(y=2, x=1)
    assert buf == ('\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                   '\x02\x00\x00\x00\x00\x00\x00\x00') # 2

def test_unordered():
    fields = [Field.new_slot('y', 1, Type.new_int64()),
              Field.new_slot('x', 0, Type.new_int64())]
    ctor = new_structor(data_size=2, ptrs_size=0, fields=fields)
    buf = ctor(x=1, y=2)
    assert buf == ('\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                   '\x02\x00\x00\x00\x00\x00\x00\x00') # 2
    buf = ctor(2, 1) # y must come first
    assert buf == ('\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                   '\x02\x00\x00\x00\x00\x00\x00\x00') # 2


def test_void():
    fields = [Field.new_slot('x', 0, Type.new_int64()),
              Field.new_slot('y', 1, Type.new_int64()),
              Field.new_slot('z', 0, Type.new_void())]
    ctor = new_structor(data_size=2, ptrs_size=0, fields=fields)
    buf = ctor(1, 2)
    assert buf == ('\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                   '\x02\x00\x00\x00\x00\x00\x00\x00') # 2


def test_tag_offset():
    ## struct Shape {
    ##   area @0 :Int64;
    ##   union {
    ##     circle @1 :Int64;      # radius
    ##     square @2 :Int64;      # width
    ##   }
    ## }
    #
    fields = [Field.new_slot('area', 0, Type.new_int64()),
              Field.new_slot('square', 1, Type.new_int64())]
    new_square = new_structor(data_size=3, ptrs_size=0,
                              fields=fields,
                              tag_offset=16, tag_value=1)
    buf = new_square(area=64, square=8)
    assert buf == ('\x40\x00\x00\x00\x00\x00\x00\x00'     # area == 64
                   '\x08\x00\x00\x00\x00\x00\x00\x00'     # square == 8
                   '\x01\x00\x00\x00\x00\x00\x00\x00')    # which() == square, padding


@py.test.mark.xfail
def test_nullable():
    isnull = field.Primitive('isnull', 0, Type.new_int64())
    value = field.NullablePrimitive('value', 8, Type.new_int64(), 0, isnull)
    fields = [isnull, value]
    ctor = new_structor(data_size=2, ptrs_size=0, fields=fields)
    buf = ctor(value=42)
    assert buf == ('\x00\x00\x00\x00\x00\x00\x00\x00'  # NOT isnull
                   '\x2a\x00\x00\x00\x00\x00\x00\x00') # 42
    #
    buf = ctor(value=None)
    assert buf == ('\x01\x00\x00\x00\x00\x00\x00\x00'  # isnull == 1
                   '\x00\x00\x00\x00\x00\x00\x00\x00') # 0
