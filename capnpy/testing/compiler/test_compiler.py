import py
import pytest
from six import b

import capnpy
from capnpy.testing.compiler.support import CompilerTest
from capnpy.compiler.compiler import CompilerError, BaseCompiler, DynamicCompiler


class TestCompilerOptions(CompilerTest):

    def test_convert_case_fields(self):
        schema = """
        @0xbf5147cbbecf40c1;
        struct MyStruct {
            firstAttr @0 :Int64;
            secondAttr @1 :Int64;
        }
        """
        mod = self.compile(schema)
        assert hasattr(mod.MyStruct, 'first_attr')
        assert hasattr(mod.MyStruct, 'second_attr')

    def test_no_convert_case(self):
        schema = """
        @0xbf5147cbbecf40c1;
        struct MyStruct {
            firstAttr @0 :Int64;
            secondAttr @1 :Int64;
        }
        """
        mod = self.compile(schema, convert_case=False)
        assert hasattr(mod.MyStruct, 'firstAttr')
        assert hasattr(mod.MyStruct, 'secondAttr')

    def test_convert_case_enum(self):
        schema = """
        @0xbf5147cbbecf40c1;
        enum Foo {
            firstItem @0;
            secondItem @1;
        }
        """
        mod = self.compile(schema)
        assert mod.Foo.first_item == 0
        assert mod.Foo.second_item == 1

    def test_name_clash(self):
        schema = """
        @0xbf5147cbbecf40c1;
        struct Types {
        }
        struct Point {
            x @0 :Int64;
            y @1 :Int64;
        }
        """
        mod = self.compile(schema)
        #
        buf = b('\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                '\x02\x00\x00\x00\x00\x00\x00\x00') # 2
        p = mod.Point.from_buffer(buf, 0, 2, 0)
        assert p.x == 1
        assert p.y == 2

    def test_keyword_as_fieldname(self):
        schema = """
        @0xbf5147cbbecf40c1;
        struct P {
            def @0 :Int64;
            if @1 :Int64;
        }
        """
        mod = self.compile(schema)
        #
        buf = b('\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                '\x02\x00\x00\x00\x00\x00\x00\x00') # 2
        p = mod.P.from_buffer(buf, 0, 2, 0)
        assert p.def_ == 1
        assert p.if_ == 2

    def test_c_type_as_fieldname(self):
        # this used to fail in pyx mode
        schema = """
        @0xbf5147cbbecf40c1;
        struct P {
            void @0 :Int64;
            int @1 :Int64;
        }
        """
        mod = self.compile(schema)
        #
        buf = b('\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                '\x02\x00\x00\x00\x00\x00\x00\x00') # 2
        p = mod.P.from_buffer(buf, 0, 2, 0)
        assert p.void == 1
        assert p.int == 2

    def test_c_type_as_fieldname_union(self):
        # this used to fail in pyx mode
        schema = """
        @0xbf5147cbbecf40c1;
        struct P {
            union {
                void @0 :Int64;
                int @1 :Int64;
            }
        }
        """
        mod = self.compile(schema)
        #
        buf = b('\x2a\x00\x00\x00\x00\x00\x00\x00'  # 42
                '\x01\x00\x00\x00\x00\x00\x00\x00') # tag == int
        p = mod.P.from_buffer(buf, 0, 2, 0)
        assert p.is_int()
        assert p.int == 42

    def test_nested_struct(self):
        schema = """
        @0xbf5147cbbecf40c1;
        struct Outer {
            struct Point {
                x @0 :Int64;
                y @1 :Int64;
            }
        }
        """
        mod = self.compile(schema)
        #
        buf = b('\x01\x00\x00\x00\x00\x00\x00\x00'  # 1
                '\x02\x00\x00\x00\x00\x00\x00\x00') # 2
        p = mod.Outer.Point.from_buffer(buf, 0, 2, 0)
        assert p.x == 1
        assert p.y == 2
        if not self.pyx:
            # unfortunately, the nice dotted name works only in pure Python
            assert mod.Outer.Point.__name__ == 'Outer.Point'

    def test_enum_within_struct(self):
        schema = """
        @0x8a1f3e2c350ebf04;

        struct Foo {
            enum Color {
                red @0;
                green @1;
                blue @2;
                yellow @3;
            }
            enum Gender {
                male @0;
                female @1;
                unknown @2;
            }
            color @0 :Color;
            gender @1 :Gender;
        }
        """
        mod = self.compile(schema)
        buf = b('\x02\x00' '\x01\x00' '\x00\x00\x00\x00')
        f = mod.Foo.from_buffer(buf, 0, 1, 0)
        assert f.color == mod.Foo.Color.blue
        assert f.gender == mod.Foo.Gender.female

    def test_two_enums_with_same_name(self):
        schema = """
        @0x8a1f3e2c350ebf04;

        struct Foo {
            enum Color {
                red @0;
                green @1;
            }
            color @0 :Color;
        }
        struct Bar {
            enum Color {
                blue @0;
                yellow @1;
            }
            color @0 :Color;
        }
        """
        mod = self.compile(schema)
        buf = b('\x01\x00' '\x00\x00\x00\x00\x00\x00')
        foo = mod.Foo.from_buffer(buf, 0, 1, 0)
        assert foo.color == mod.Foo.Color.green
        bar = mod.Bar.from_buffer(buf, 0, 1, 0)
        assert bar.color == mod.Bar.Color.yellow

    def test_const(self):
        schema = """
        @0xbf5147cbbecf40c1;
        struct Foo {
            const bar :UInt16 = 42;
            const baz :Text = "baz";
        }
        """
        mod = self.compile(schema)
        assert mod.Foo.bar == 42
        assert mod.Foo.baz == b'baz'

    def test_global_const(self):
        schema = """
        @0xbf5147cbbecf40c1;
        const bar :UInt16 = 42;
        const baz :Text = "baz";
        """
        mod = self.compile(schema)
        assert mod.bar == 42
        assert mod.baz == b'baz'

    def test_global_options(self):
        schema = """
        @0xbf5147cbbecf40c1;
        using Py = import "/capnpy/annotate.capnp";
        $Py.options(convertCase=false);

        struct MyStruct {
            firstAttr @0 :Int64;
            secondAttr @1 :Int64;
        }
        """
        mod = self.compile(schema, convert_case=True)
        # check that the $Py.options annotation has a greater precedence than
        # the default options
        assert hasattr(mod.MyStruct, 'firstAttr')
        assert hasattr(mod.MyStruct, 'secondAttr')

    def test_struct_and_field_options(self):
        schema = """
        @0xbf5147cbbecf40c1;
        using Py = import "/capnpy/annotate.capnp";
        $Py.options(convertCase=false);

        struct A $Py.options(convertCase=true) {
            firstAttr @0 :Int64;
            secondAttr @1 :Int64 $Py.options(convertCase=false);
        }

        struct B {
            firstAttr @0 :Int64;
            secondAttr @1 :Int64 $Py.options(convertCase=true);
        }
        """
        mod = self.compile(schema, convert_case=True)
        # check that the $Py.options annotation has a greater precedence than
        # the default options
        assert hasattr(mod.A, 'first_attr')
        assert hasattr(mod.A, 'secondAttr')
        #
        assert hasattr(mod.B, 'firstAttr')
        assert hasattr(mod.B, 'second_attr')


class TestCapnpExcecutable(CompilerTest):

    def test_capnp_not_found(self, monkeypatch):
        schema = """
        @0xbf5147cbbecf40c1;
        """
        monkeypatch.setenv('PATH', str(self.tmpdir))
        exc = py.test.raises(CompilerError, "self.compile(schema)")
        assert str(exc.value).startswith('Cannot find the capnp executable')

    def test_capnp_too_old(self, monkeypatch):
        self.write('capnp', """\
        #!/bin/bash

        if [ "X$1" = "X--version" ]
        then
            echo "Cap'n Proto version 0.4.0"
        else
            echo "Error: the only allowed option is --version, got $*"
            #exit 1
        fi
        """).chmod(0o755)
        #
        schema = """
        @0xbf5147cbbecf40c1;
        """
        monkeypatch.setenv('PATH', str(self.tmpdir))
        exc = py.test.raises(CompilerError, "self.compile(schema)")
        assert str(exc.value).startswith('The capnp executable is too old')

    def test_capnp_path(self, tmpdir):
        class MyFakeCompiler(BaseCompiler):
            def _exec(self, *cmd):
                return cmd

            def _capnp_check_version(self):
                return True

        d1 = tmpdir.ensure('mydir1', dir=True)
        d2 = tmpdir.ensure('mydir2', dir=True)
        f1 = tmpdir.ensure('myfile1', file=True)
        path = [tmpdir.join('mydir1'),
                tmpdir.join('mydir2'),
                tmpdir.join('myfile')]
        comp = MyFakeCompiler(path)
        cmd = comp._capnp_compile('myschema.capnp')
        # check that myfile is NOT included in the -I options
        assert cmd == (
            'capnp',
            'compile',
            '-o-',
            '-I%s' % d1,
            '-I%s' % d2,
            'myschema.capnp')

class TestDynamicCompiler(object):

    def test_parse_schema(self, tmpdir):
        schema = """
        @0xbf5147cbbecf40c1;
        struct Point {
            x @0 :Int64;
            y @1 :Int64;
        }
        """
        filename = tmpdir.join('foo.capnp')
        filename.write(schema)
        comp = DynamicCompiler([])
        req = comp.parse_schema(filename=filename)
        assert req.requestedFiles[0].filename == str(filename).encode()
