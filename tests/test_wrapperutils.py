#!/usr/bin/env python
#
# test_wrapperutils.py -
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#

import os
import shlex

import pytest

import numpy as np
import nibabel as nib

import fsl.utils.tempdir         as tempdir
import fsl.wrappers.wrapperutils as wutils


def test_applyArgStyle():

    kwargs = {
        'name'  : 'val',
        'name2' : ['val1', 'val2'],
    }

    # these combinations of style+valsep should
    # raise an error
    with pytest.raises(ValueError):
        wutils.applyArgStyle(style='-=',  valsep=' ', **kwargs)
    with pytest.raises(ValueError):
        wutils.applyArgStyle(style='--=', valsep=' ', **kwargs)

    # unsupported style/valsep
    with pytest.raises(ValueError):
        wutils.applyArgStyle('?', **kwargs)
    with pytest.raises(ValueError):
        wutils.applyArgStyle('-', valsep='b', **kwargs)

    # style, valsep, expected_result.
    # Order of arguments is not guaranteed
    tests = [
        ('-',   ' ', [' -name  val', '-name2   val1 val2']),
        ('-',   '"', [' -name  val', '-name2  "val1 val2"']),
        ('-',   ',', [' -name  val', '-name2   val1,val2']),

        ('--',  ' ', ['--name  val', '--name2  val1 val2']),
        ('--',  '"', ['--name  val', '--name2 "val1 val2"']),
        ('--',  ',', ['--name  val', '--name2  val1,val2']),

        ('-=',  '"', [' -name=val', '-name2="val1 val2"']),
        ('-=',  ',', [' -name=val', '-name2=val1,val2']),

        ('--=', '"', ['--name=val', '--name2="val1 val2"']),
        ('--=', ',', ['--name=val', '--name2=val1,val2']),
    ]

    for style, valsep, exp in tests:
        exp    = [shlex.split(e) for e in exp]
        result = wutils.applyArgStyle(style, valsep=valsep, **kwargs)

        assert result in (exp[0] + exp[1], exp[1] + exp[0])


def test_applyArgStyle_argmap():

    kwargs = {
        'name1' : 'val1',
        'name2' : 'val2',
    }

    argmap = {
        'name1' : 'n',
        'name2' : 'm',
    }

    # order not guaranteed
    exp = [shlex.split('-n val1 -m val2'),
           shlex.split('-m val2 -n val1')]

    assert wutils.applyArgStyle('-', argmap=argmap, **kwargs) in exp


def test_applyArgStyle_valmap():

    valmap = {
        'a' : wutils.SHOW_IF_TRUE,
        'b' : wutils.HIDE_IF_TRUE,
    }

    # kwargs, expected
    tests = [
        ({                          }, ['']),
        ({ 'a' : False,             }, ['']),
        ({ 'a' : True,              }, ['-a']),
        ({              'b' : False }, ['-b']),
        ({              'b' : True  }, ['']),
        ({ 'a' : False, 'b' : True  }, ['']),
        ({ 'a' : True,  'b' : True  }, ['-a']),
        ({ 'a' : False, 'b' : False }, ['-b']),
        ({ 'a' : False, 'b' : True  }, ['']),
        ({ 'a' : True,  'b' : False }, ['-a -b', '-b -a']),
        ({ 'a' : True,  'b' : True  }, ['-a']),
    ]

    for kwargs, expected in tests:
        expected = [shlex.split(e) for e in expected]
        assert wutils.applyArgStyle('-', valmap=valmap, **kwargs) in expected


def test_applyArgStyle_argmap_valmap():

    argmap = {'a1' : 'a', 'a2' : 'b'}
    valmap = {
        'a' : wutils.SHOW_IF_TRUE,
        'b' : wutils.HIDE_IF_TRUE,
    }

    # kwargs, expected
    tests = [
        ({                            }, ['']),
        ({ 'a1' : False,              }, ['']),
        ({ 'a1' : True,               }, ['-a']),
        ({               'a2' : False }, ['-b']),
        ({               'a2' : True  }, ['']),
        ({ 'a1' : False, 'a2' : True  }, ['']),
        ({ 'a1' : True,  'a2' : True  }, ['-a']),
        ({ 'a1' : False, 'a2' : False }, ['-b']),
        ({ 'a1' : False, 'a2' : True  }, ['']),
        ({ 'a1' : True,  'a2' : False }, ['-a -b', '-b -a']),
        ({ 'a1' : True,  'a2' : True  }, ['-a']),
    ]

    for kwargs, expected in tests:
        expected = [shlex.split(e) for e in expected]
        assert wutils.applyArgStyle(
            '-', argmap=argmap, valmap=valmap, **kwargs) in expected


def test_namedPositionals():
    def func1(): pass
    def func2(a, b, c): pass
    def func3(a, b, c, d=None, e=None): pass
    def func4(*args): pass
    def func5(*args, **kwargs): pass
    def func6(a, b, *args): pass
    def func7(a, b, *args, **kwargs): pass

    tests = [
        (func1, [],        []),
        (func2, [1, 2, 3], ['a', 'b', 'c']),
        (func3, [1, 2, 3], ['a', 'b', 'c']),
        (func4, [1, 2, 3], ['args0', 'args1', 'args2']),
        (func5, [1, 2, 3], ['args0', 'args1', 'args2']),
        (func6, [1, 2, 3], ['a', 'b', 'args0']),
        (func7, [1, 2, 3], ['a', 'b', 'args0']),
    ]

    for func, args, expected in tests:
        result = wutils.namedPositionals(func, args)
        assert list(result) == list(expected)

# TODO
#  - test _FileOrImage LOAD tuple order



def test_fileOrArray():

    @wutils.fileOrArray('arr1', 'other', 'output')
    def func(arr1, **kwargs):
        arr1  = np.loadtxt(arr1)
        other = np.loadtxt(kwargs['other'])
        np.savetxt(kwargs['output'], (arr1 * other))

    with tempdir.tempdir():

        arr1     = np.array([[1,  2], [ 3,  4]])
        other    = np.array([[5,  6], [ 7,  8]])
        expected = np.array([[5, 12], [21, 32]])
        np.savetxt('arr1.txt',  arr1)
        np.savetxt('other.txt', other)

        # file  file  file
        func('arr1.txt', other='other.txt', output='output.txt')
        assert np.all(np.loadtxt('output.txt') == expected)
        os.remove('output.txt')

        # file  file  array
        result = func('arr1.txt', other='other.txt', output=wutils.LOAD)['output']
        assert np.all(result == expected)

        # file  array file
        func('arr1.txt', other=other, output='output.txt')
        assert np.all(np.loadtxt('output.txt') == expected)
        os.remove('output.txt')

        # file  array array
        result = func('arr1.txt', other=other, output=wutils.LOAD)['output']
        assert np.all(result == expected)

        # array file  file
        func(arr1, other='other.txt', output='output.txt')
        assert np.all(np.loadtxt('output.txt') == expected)
        os.remove('output.txt')

        # array file  array
        result = func(arr1, other='other.txt', output=wutils.LOAD)['output']
        assert np.all(result == expected)

        # array array file
        func(arr1, other=other, output='output.txt')
        assert np.all(np.loadtxt('output.txt') == expected)
        os.remove('output.txt')

        # array array array
        result = func(arr1, other=other, output=wutils.LOAD)['output']
        assert np.all(result == expected)


def test_fileOrImage():

    @wutils.fileOrImage('img1', 'img2', 'output')
    def func(img1, **kwargs):
        img1   = nib.load(img1).get_data()
        img2   = nib.load(kwargs['img2']).get_data()
        output = nib.nifti1.Nifti1Image(img1 * img2, np.eye(4))
        nib.save(output, kwargs['output'])

    with tempdir.tempdir():

        img1     = nib.nifti1.Nifti1Image(np.array([[1,  2], [ 3,  4]]), np.eye(4))
        img2     = nib.nifti1.Nifti1Image(np.array([[5,  6], [ 7,  8]]), np.eye(4))
        expected = np.array([[5, 12], [21, 32]])
        nib.save(img1, 'img1.nii')
        nib.save(img2, 'img2.nii')

        # file  file  file
        func('img1.nii', img2='img2.nii', output='output.nii')
        assert np.all(nib.load('output.nii').get_data() == expected)
        os.remove('output.nii')

        # file  file  array
        result = func('img1.nii', img2='img2.nii', output=wutils.LOAD)['output']
        assert np.all(result.get_data() == expected)

        # file  array file
        func('img1.nii', img2=img2, output='output.nii')
        assert np.all(nib.load('output.nii').get_data() == expected)
        os.remove('output.nii')

        # file  array array
        result = func('img1.nii', img2=img2, output=wutils.LOAD)['output']
        assert np.all(result.get_data() == expected)

        # array file  file
        func(img1, img2='img2.nii', output='output.nii')
        assert np.all(nib.load('output.nii').get_data() == expected)
        os.remove('output.nii')

        # array file  array
        result = func(img1, img2='img2.nii', output=wutils.LOAD)['output']
        assert np.all(result.get_data() == expected)

        # array array file
        func(img1, img2=img2, output='output.nii')
        assert np.all(nib.load('output.nii').get_data() == expected)
        os.remove('output.nii')

        # array array array
        result = func(img1, img2=img2, output=wutils.LOAD)['output']
        assert np.all(result.get_data() == expected)


def test_chained_fileOrImageAndArray():
    @wutils.fileOrImage('image')
    @wutils.fileOrArray('array')
    def func(image, array):
        nib.load(image)
        np.loadtxt(array)

    image = nib.nifti1.Nifti1Image(np.array([[1,  2], [ 3,  4]]), np.eye(4))
    array = np.array([[5, 6, 7, 8]])

    with tempdir.tempdir():

        nib.save(image, 'image.nii')
        np.savetxt('array.txt', array)

        func('image.nii', 'array.txt')
        func('image.nii',  array)
        func( image,      'array.txt')
        func( image,       array)
