#!/usr/bin/env python
#
# transform.py - Functions for working with affine transformation matrices.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides functions related to 3D image transformations and
spaces. The following functions are provided:

.. autosummary::
   :nosignatures:

   transform
   scaleOffsetXform
   invert
   concat
   compse
   decompose
   rotMatToAxisAngles
   axisAnglesToRotMat
   axisBounds
   flirtMatrixToSform
"""

import numpy        as np
import numpy.linalg as linalg
import collections


def invert(x):
    """Inverts the given matrix using ``numpy.linalg.inv``. """
    return linalg.inv(x)


def concat(*xforms):
    """Combines the given matrices (returns the dot product)."""

    result = xforms[0]

    for i in range(1, len(xforms)):
        result = np.dot(result, xforms[i])

    return result


def scaleOffsetXform(scales, offsets):
    """Creates and returns an affine transformation matrix which encodes
    the specified scale(s) and offset(s).

    
    :arg scales:  A tuple of up to three values specifying the scale factors
                  for each dimension. If less than length 3, is padded with
                  ``1.0``.

    :arg offsets: A tuple of up to three values specifying the offsets for
                  each dimension. If less than length 3, is padded with
                  ``0.0``.

    :returns:     A ``numpy.float32`` array of size :math:`4 \\times 4`.
    """

    if not isinstance(scales,  collections.Sequence): scales  = [scales]
    if not isinstance(offsets, collections.Sequence): offsets = [offsets]

    lens = len(scales)
    leno = len(offsets)

    if lens < 3: scales  = scales  + [1.0] * (3 - lens)
    if leno < 3: offsets = offsets + [0.0] * (3 - leno)

    xform = np.eye(4, dtype=np.float64)

    xform[0, 0] = scales[0]
    xform[1, 1] = scales[1]
    xform[2, 2] = scales[2]

    xform[0, 3] = offsets[0]
    xform[1, 3] = offsets[1]
    xform[2, 3] = offsets[2]

    return xform


def compose(scales, offsets, rotations, origin=None):
    """Compose a transformation matrix out of the given scales, offsets
    and axis rotations.

    :arg scales:    Sequence of three scale values.
    
    :arg offsets:   Sequence of three offset values.
    
    :arg rotations: Sequence of three rotation values, in radians.
    
    :arg origin:    Origin of rotation - must be scaled by the ``scales``.
                    If not provided, the rotation origin is ``(0, 0, 0)``.
    """

    preRotate  = np.eye(4)
    postRotate = np.eye(4)
    if origin is not None:
        preRotate[ 0, 3] = -origin[0]
        preRotate[ 1, 3] = -origin[1]
        preRotate[ 2, 3] = -origin[2]
        postRotate[0, 3] =  origin[0]
        postRotate[1, 3] =  origin[1]
        postRotate[2, 3] =  origin[2] 

    scale  = np.eye(4, dtype=np.float64)
    offset = np.eye(4, dtype=np.float64)
    rotate = np.eye(4, dtype=np.float64)
    
    scale[  0,  0] = scales[ 0]
    scale[  1,  1] = scales[ 1]
    scale[  2,  2] = scales[ 2]
    offset[ 0,  3] = offsets[0]
    offset[ 1,  3] = offsets[1]
    offset[ 2,  3] = offsets[2]
    rotate[:3, :3] = axisAnglesToRotMat(*rotations)

    return concat(offset, postRotate, rotate, preRotate, scale)


def decompose(xform):
    """Decomposes the given transformation matrix into separate offsets,
    scales, and rotations.

    .. note:: Shears are not yet supported, and may never be supported.
    """

    offsets = xform[:3, 3]
    scales  = [np.sqrt(np.sum(xform[:3, 0] ** 2)),
               np.sqrt(np.sum(xform[:3, 1] ** 2)),
               np.sqrt(np.sum(xform[:3, 2] ** 2))]
    
    rotmat         = np.copy(xform[:3, :3])
    rotmat[:, 0] /= scales[0]
    rotmat[:, 1] /= scales[1]
    rotmat[:, 2] /= scales[2]

    rots = rotMatToAxisAngles(rotmat)

    return scales, offsets, rots


def rotMatToAxisAngles(rotmat):
    """Given a ``(3, 3)`` rotation matrix, decomposes the rotations into
    an angle in radians about each axis.
    """
    xrot = np.arctan2(rotmat[2, 1], rotmat[2, 2])
    yrot = np.sqrt(   rotmat[2, 1] ** 2 + rotmat[2, 2] ** 2)
    yrot = np.arctan2(rotmat[2, 0], yrot)
    zrot = np.arctan2(rotmat[1, 0], rotmat[0, 0])

    return [xrot, yrot, zrot]


def axisAnglesToRotMat(xrot, yrot, zrot):
    """Constructs a ``(3, 3)`` rotation matrix from the given angles, which
    must be specified in radians.
    """ 

    xmat = np.eye(3)
    ymat = np.eye(3)
    zmat = np.eye(3)
    
    xmat[1, 1] =  np.cos(xrot)
    xmat[1, 2] = -np.sin(xrot)
    xmat[2, 1] =  np.sin(xrot)
    xmat[2, 2] =  np.cos(xrot)

    ymat[0, 0] =  np.cos(yrot)
    ymat[0, 2] =  np.sin(yrot)
    ymat[2, 0] = -np.sin(yrot)
    ymat[2, 2] =  np.cos(yrot)

    zmat[0, 0] =  np.cos(zrot)
    zmat[0, 1] = -np.sin(zrot)
    zmat[1, 0] =  np.sin(zrot)
    zmat[1, 1] =  np.cos(zrot)

    return concat(zmat, ymat, xmat)


def axisBounds(shape,
               xform,
               axes=None,
               origin='centre',
               boundary='high',
               offset=1e-4):
    """Returns the ``(lo, hi)`` bounds of the specified axis/axes in the
    world coordinate system defined by ``xform``.
    
    If the ``origin`` parameter is set to  ``centre`` (the default),
    this function assumes that voxel indices correspond to the voxel
    centre. For example, the voxel at ``(4, 5, 6)`` covers the space:
    
      ``[3.5 - 4.5, 4.5 - 5.5, 5.5 - 6.5]``
    
    So the bounds of the specified shape extends from the corner at

      ``(-0.5, -0.5, -0.5)``

    to the corner at

      ``(shape[0] - 0.5, shape[1] - 0.5, shape[1] - 0.5)``

    If the ``origin`` parameter is set to ``corner``, this function
    assumes that voxel indices correspond to the voxel corner. In this
    case, a voxel  at ``(4, 5, 6)`` covers the space:
    
      ``[4 - 5, 5 - 6, 6 - 7]``
    
    So the bounds of the specified shape extends from the corner at

      ``(0, 0, 0)``

    to the corner at

      ``(shape[0], shape[1], shape[1])``.


    If the ``boundary`` parameter is set to ``high``, the high voxel bounds
    are reduced by a small amount (specified by the ``offset`` parameter)
    before they are transformed to the world coordinate system.  If
    ``boundary`` is set to ``low``, the low bounds are increased by a small
    amount.  The ``boundary`` parameter can also be set to ``'both'``, or
    ``None``. This option is provided so that you can ensure that the
    resulting bounds will always be contained within the image space.
    
    :arg shape:    The ``(x, y, z)`` shape of the data.

    :arg xform:    Transformation matrix which transforms voxel coordinates
                   to the world coordinate system.

    :arg axes:     The world coordinate system axis bounds to calculate.

    :arg origin:   Either ``'centre'`` (the default) or ``'origin'``.

    :arg boundary: Either ``'high'`` (the default), ``'low'``, ''`both'``,
                   or ``None``. 

    :arg offset:   Amount by which the boundary voxel coordinates should be
                   offset. Defaults to ``1e-4``.

    :returns:      A list of tuples, one for each axis specified in the 
                   ``axes`` argument. Each tuple contains the ``(lo, hi)`` 
                   bounds of the corresponding world coordinate system axis.
    """

    origin = origin.lower()

    # lousy US spelling
    if origin == 'center':
        origin = 'centre'

    if origin not in ('centre', 'corner'):
        raise ValueError('Invalid origin value: {}'.format(origin))

    scalar = False

    if axes is None:
        axes = [0, 1, 2]
        
    elif not isinstance(axes, collections.Iterable):
        scalar = True
        axes   = [axes]
    
    x, y, z = shape[:3]

    points = np.zeros((8, 3), dtype=np.float32)

    if origin == 'centre':
        x0 = -0.5
        y0 = -0.5
        z0 = -0.5
        x -=  0.5
        y -=  0.5
        z -=  0.5
    else:
        x0 = 0
        y0 = 0
        z0 = 0

    if boundary in ('low', 'both'):
        x0 += offset
        y0 += offset
        z0 += offset
        
    if boundary in ('high', 'both'):
        x  -= offset
        y  -= offset
        z  -= offset

    points[0, :] = [x0, y0, z0]
    points[1, :] = [x0, y0,  z]
    points[2, :] = [x0,  y, z0]
    points[3, :] = [x0,  y,  z]
    points[4, :] = [x,  y0, z0]
    points[5, :] = [x,  y0,  z]
    points[6, :] = [x,   y, z0]
    points[7, :] = [x,   y,  z]

    tx = transform(points, xform)

    lo = tx[:, axes].min(axis=0)
    hi = tx[:, axes].max(axis=0)

    if scalar: return (lo[0], hi[0])
    else:      return (lo,    hi)

        
def transform(p, xform, axes=None):
    """Transforms the given set of points ``p`` according to the given affine
    transformation ``xform``. 

    
    :arg p:     A sequence or array of points of shape :math:`N \\times  3`.

    :arg xform: An affine transformation matrix with which to transform the
                points in ``p``.

    :arg axes:  If you are only interested in one or two axes, and the source
                axes are orthogonal to the target axes (see the note below),
                you may pass in a 1D, ``N*1``, or ``N*2`` array as ``p``, and
                use this argument to specify which axis/axes that the data in
                ``p`` correspond to.

    :returns:   The points in ``p``, transformed by ``xform``, as a ``numpy``
                array with the same data type as the input.


    .. note:: The ``axes`` argument should only be used if the source
              coordinate system (the points in ``p``) axes are orthogonal
              to the target coordinate system (defined by the ``xform``).

              In other words, you can only use the ``axes`` argument if
              the ``xform`` matrix consists solely of translations and
              scalings.
    """

    p  = _fillPoints(p, axes)
    t  = np.dot(xform[:3, :3], p.T).T + xform[:3, 3]

    if axes is not None:
        t = t[:, axes]

    if t.size == 1: return t[0]
    else:           return t


def _fillPoints(p, axes):
    """Used by the :func:`transform` function. Turns the given array p into
    a ``N*3`` array of ``x,y,z`` coordinates. The array p may be a 1D array,
    or an ``N*2`` or ``N*3`` array.
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


def flirtMatrixToSform(flirtMat, srcImage, refImage):
    """Converts the given ``FLIRT`` transformation matrix into a
    transformation from the source image voxel coordinate system to
    the reference image world coordinate system.

    FLIRT transformation matrices transform from the source image scaled voxel
    coordinate system into the reference image scaled voxel coordinate system
    (voxels scaled by pixdims, with a left-right flip if the image sform has a
    positive determinant).

    So to construct a transformation from source image voxel coordinates
    into reference image world coordinates, we need to combine the following:

      1. Source voxels -> Source scaled voxels
      2. Source scaled voxels -> Reference scaled voxels (the FLIRT matrix)
      3. Reference scaled voxels -> Reference voxels
      4. Reference voxels -> Reference world (the reference image sform)

    :arg flirtMat: A ``(4, 4)`` transformation matrix
    :arg srcImage: Source :class:`.Image`
    :arg refImage: Reference :class:`.Image`
    """
    
    srcScaledVoxelMat    = srcImage.voxelsToScaledVoxels()
    refScaledVoxelMat    = refImage.voxelsToScaledVoxels()
    refVoxToWorldMat     = refImage.voxToWorldMat
    refInvScaledVoxelMat = invert(refScaledVoxelMat)

    return concat(refVoxToWorldMat,
                  refInvScaledVoxelMat,
                  flirtMat,
                  srcScaledVoxelMat)
