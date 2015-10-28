#!/usr/bin/env python
#
# melodicresults.py - Utility functions for loading/querying the contents of a
# MELODIC analysis directory.
# 
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides a set of functions for accessing the contents of a
MELODIC analysis directory. These functions are primarily intended to be used
by the :class:`.MELODICImage` class, but are available for other uses. The
following functions are provided:

.. autosummary::
   nosignatures:

   isMelodicDir
   getMelodicDir
   getTopLevelAnalysisDir
   getDataFile
   getICFile
   getMixFile
   getNumComponents
   getComponentTimeSeries
"""


import os.path as op
import numpy   as np

import fsl.data.image       as fslimage
import fsl.data.featresults as featresults


def isMelodicDir(path):
    """Returns ``True`` if the given path looks like it is contained within
    a MELODIC directory, ``False`` otherwise. 
    """

    # Must be named *.ica or *.gica
    return getMelodicDir(path) is not None

    
def getMelodicDir(path):
    """Returns the MELODIC directory in which the given path is contained,
    or ``None`` if it is not contained within a MELODIC directory. A melodic
    directory:

      - Must be named ``*.ica`` or ``*.gica``
      - Must contain a file called ``melodic_IC.nii.gz``
      - Must contain a file called ``melodic_mix``.
    """

    # TODO This code is identical to featresults.getFEATDir.
    # Can you generalise it and put it somewhere in fsl.utils?

    path     = op.abspath(path)

    sufs     = ['.ica', '.gica']
    idxs     = [(path.rfind(s), s) for s in sufs]
    idx, suf = max(idxs, key=lambda (i, s): i)

    if idx == -1:
        return None

    idx  += len(suf)
    path  = path[:idx].rstrip(op.sep)

    if not path.endswith(suf):
        return None

    # Must contain an image file called melodic_IC
    try:
        fslimage.addExt(op.join(path, 'melodic_IC'), mustExist=True)
    except ValueError:
        return None

    # Must contain a file called melodic_mix
    if not op.exists(op.join(path, 'melodic_mix')):
        return None
                                           
    return path


def getTopLevelAnalysisDir(path):
    """If the given path is a MELODIC directory, and it is contained within
    a FEAT directory, or another MELODIC directory, the path to the latter
    directory is returned. Otherwise, ``None`` is returned.
    """

    meldir = getMelodicDir(path)
    sufs   =  ['.feat', '.gfeat', '.ica', '.gica']
    
    if meldir is None:
        return None

    if featresults.isFEATDir(meldir):
        return featresults.getFEATDir(meldir)

    parentDir = op.dirname(meldir)
    parentDir = parentDir.rstrip(op.sep)

    if not any([parentDir.endswith(s) for s in sufs]):
        return None

    # Must contain a file called filtered_func_data.nii.gz
    dataFile = op.join(parentDir, 'filtered_func_data')

    try:
        dataFile = fslimage.addExt(dataFile, mustExist=True)
    except ValueError:
        return None

    return parentDir

    
def getDataFile(meldir):
    """If the given melodic directory is contained within another analysis
    directory, the path to the data file is returned. Otherwise ``None`` is
    returned.
    """

    topDir = getTopLevelAnalysisDir(meldir)

    if topDir is None:
        return None

    dataFile = op.join(topDir, 'filtered_func_data')

    try:
        return fslimage.addExt(dataFile, mustExist=True)
    except ValueError:
        return None


def getICFile(meldir):
    """Returns the path to the melodic IC image. """
    return fslimage.addExt(op.join(meldir, 'melodic_IC'))


def getMixFile(meldir):
    """Returns the path to the melodic mix file. """
    return op.join(meldir, 'melodic_mix')


def getNumComponents(meldir):
    """Returns the number of components generated in the melodic analysis
    contained in the given directrory.
    """

    icImg = fslimage.Image(getICFile(meldir), loadData=False)
    return icImg.shape[3]


def getComponentTimeSeries(meldir):
    """Returns a ``numpy`` array containing the melodic mix for the given
    directory.
    """

    mixfile = getMixFile(meldir)
    return np.loadtxt(mixfile)
