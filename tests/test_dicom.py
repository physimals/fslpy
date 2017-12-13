#!/usr/bin/env python
#
# test_dicom.py -
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#

import os.path as op
import            tarfile

import mock
import pytest

import fsl.data.dicom    as fsldcm
import fsl.utils.tempdir as tempdir

from . import tempdir


datadir = op.join(op.dirname(__file__), 'testdata')


def setup_module():

    if not fsldcm.enabled():
        raise RuntimeError('dcm2niix is not present - tests cannot be run')


def test_disabled():

    with mock.patch('fsl.data.dicom.enabled', return_value=False):
        with pytest.raises(RuntimeError):
            fsldcm.scanDir('.')
        with pytest.raises(RuntimeError):
            fsldcm.loadSeries({})


def test_enabled():

    try:
        fsldcm.enabled.invalidate()
        assert fsldcm.enabled()
        fsldcm.enabled.invalidate()
        # test dcm2niix not present
        with mock.patch('subprocess.check_output',
                        side_effect=FileNotFoundError()):
            assert not fsldcm.enabled()

        # test presence of different versions
        tests = [(b'version v2.1.20191212', True),
                 (b'version v1.0.20160930', True),
                 (b'version v1.0.20160929', False),
                 (b'version v0.0.00000000', False),
                 (b'version blurgh',        False)]

        for verstr, expected in tests:
            fsldcm.enabled.invalidate()
            with mock.patch('subprocess.check_output', return_value=verstr):
                assert fsldcm.enabled() == expected

    finally:
        fsldcm.enabled.invalidate()


def test_scanDir():

    with tempdir() as td:

        series = fsldcm.scanDir(td)
        assert len(series) == 0

        datafile = op.join(datadir, 'example_dicom.tbz2')

        with tarfile.open(datafile) as f:
            f.extractall()

        series = fsldcm.scanDir(td)
        assert len(series) == 2

        for s in series:
            assert s['PatientName'] == 'MCCARTHY_PAUL'


def test_loadSeries():

    with tempdir() as td:

        datafile = op.join(datadir, 'example_dicom.tbz2')

        with tarfile.open(datafile) as f:
            f.extractall()

        series = fsldcm.scanDir(td)

        expShapes = [(512, 512, 25),
                     (512, 512, 29)]

        for s, expShape in zip(series, expShapes):

            img = fsldcm.loadSeries(s)

            assert len(img) == 1

            img = img[0]

            assert img.shape              == expShape
            assert img.get('PatientName') == 'MCCARTHY_PAUL'
            assert 'PatientName'                    in img.keys()
            assert 'MCCARTHY_PAUL'                  in img.values()
            assert ('PatientName', 'MCCARTHY_PAUL') in img.items()