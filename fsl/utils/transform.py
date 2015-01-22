#!/usr/bin/env python
#
# transform.py - Functions for working with affine transformation matrices.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides functions related to 3D image transformations and
spaces.
"""

import numpy        as np
import numpy.linalg as linalg
import collections


def invert(x):
    """Inverts the given matrix. """
    return linalg.inv(x)


def concat(x1, x2):
    """Combines the two matrices (returns the dot product)."""
    return np.dot(x1, x2)


def scaleOffsetXform(scales, offsets):
    """Creates and returns an affine transformation matrix which encodes
    the specified scale(s) and offset(s).
    """

    if not isinstance(scales,  collections.Sequence): scales  = [scales]
    if not isinstance(offsets, collections.Sequence): offsets = [offsets]

    lens = len(scales)
    leno = len(offsets)

    if lens < 3: scales  = scales  + [1] * (3 - lens)
    if leno < 3: offsets = offsets + [0] * (3 - leno)

    xform = np.eye(4, dtype=np.float32)

    xform[0, 0] = scales[0]
    xform[1, 1] = scales[1]
    xform[2, 2] = scales[2]

    xform[3, 0] = offsets[0]
    xform[3, 1] = offsets[0]
    xform[3, 2] = offsets[0]

    return xform


def axisBounds(shape, xform, axes=None):
    """Returns the (lo, hi) bounds of the specified axis/axes."""

    scalar = False

    if axes is None:
        axes = [0, 1, 2]
        
    elif not isinstance(axes, collections.Iterable):
        scalar = True
        axes   = [axes]
    
    x, y, z = shape[:3]

    x -= 0.5
    y -= 0.5
    z -= 0.5

    points = np.zeros((8, 3), dtype=np.float32)

    points[0, :] = [-0.5, -0.5, -0.5]
    points[1, :] = [-0.5, -0.5,  z]
    points[2, :] = [-0.5,  y,   -0.5]
    points[3, :] = [-0.5,  y,    z]
    points[4, :] = [x,    -0.5, -0.5]
    points[5, :] = [x,    -0.5,  z]
    points[6, :] = [x,     y,   -0.5]
    points[7, :] = [x,     y,    z]

    tx = transform(points, xform)

    lo = tx[:, axes].min(axis=0)
    hi = tx[:, axes].max(axis=0)

    if scalar: return (lo[0], hi[0])
    else:      return (lo,    hi)


def axisLength(shape, xform, axis):
    """Return the length, in real world units, of the specified axis.
    """
        
    points          = np.zeros((2, 3), dtype=np.float32)
    points[:]       = [-0.5, -0.5, -0.5]
    points[1, axis] = shape[axis] - 0.5 

    tx = transform(points, xform)

    # euclidean distance between each boundary point
    return sum((tx[0, :] - tx[1, :]) ** 2) ** 0.5 

        
def transform(p, xform, axes=None):
    """Transforms the given set of points ``p`` according to the given affine
    transformation ``x``. The transformed points are returned as a
    :class:``numpy.float64`` array.
    """

    p = _fillPoints(p, axes)
    t = np.dot(xform[:3, :3].T, p.T).T  + xform[3, :3]

    if axes is not None:
        t = t[:, axes]

    if t.size == 1: return t[0]
    else:           return t


def _fillPoints(p, axes):
    """Used by the :func:`transform` function. Turns the given array p into
    a N*3 array of x,y,z coordinates. The array p may be a 1D array, or an
    N*2 or N*3 array.
    """

    if not isinstance(p, collections.Iterable): p = [p]
    
    p = np.array(p)

    if axes is None: return p

    if not isinstance(axes, collections.Iterable): axes = [axes]

    if p.ndim == 1:
        p = p.reshape((len(p), 1))

    if p.ndim != 2:
        raise ValueError('Points array must be either one or two '
                         'dimensions')

    if len(axes) != p.shape[1]:
        raise ValueError('Points array shape does not match specified '
                         'number of axes')

    newp = np.zeros((len(p), 3), dtype=p.dtype)

    for i, ax in enumerate(axes):
        newp[:, ax] = p[:, i]

    return newp
