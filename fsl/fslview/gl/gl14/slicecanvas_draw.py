#!/usr/bin/env python
#
# slicecanvas_draw.py - Render slices from a collection of images in an OpenGL
#                       1.4 compatible manner.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""Render slices from a collection of images in an OpenGL 1.4 compatible
 manner, using immediate mode rendering. 

.. note:: This module is extremely tightly coupled to the
:class:`~fsl.fslview.gl.slicecanvas.SliceCanvas` class, and to the
:class:`~fsl.fslview.gl.gl14.glimagedata.GLImageData` class.

This module provides two functions:

  - :func:`drawScene` draws slices from all of the images in an
    :class:`~fsl.data.image.ImageList` to a
    :class:`~fsl.fslview.gl.slicecanvas.SliceCanvas` display.

  - :func:`drawSlice` (used by :func:`drawScene`) draws slices from one image
    to the :class:`~fsl.fslview.gl.slicecanvas.SliceCanvas`.
"""

import logging

log = logging.getLogger(__name__)

import scipy.interpolate as interp
import numpy             as np
import OpenGL.GL         as gl
        
def drawSlice(canvas, image, zpos, xform=None):
    """Draws the specified slice from the specified image on the canvas.

    If ``xform`` is not provided, the
    :class:`~fsl.data.image.Image` ``voxToWorldMat`` transformation
    matrix is used.

    :arg image:   The :class:`~fsl.data.image.Image` object to draw.
    
    :arg zpos:    World Z position of slice to be drawn.
    
    :arg xform:   A 4*4 transformation matrix to be applied to the slice
                  data (or ``None`` to use the
                  :class:`~fsl.data.image.Image` ``voxToWorldMat``
                  matrix).
    """

    # The GL data is stored as an attribute of the image,
    # and is created in the SliceCanvas._imageListChanged
    # method when images are added to the image. If there's
    # no data here, ignore it; hopefully by the time the
    # image is to be drawn again, it will have been created.
    try:    glImageData = image.getAttribute(canvas.name)
    except: return
    
    imageDisplay = image.getAttribute('display')
    
    # Don't draw the slice if this
    # image display is disabled
    if not imageDisplay.enabled: return

    worldCoords = glImageData.worldCoords
    texCoords   = glImageData.texCoords
    
    worldCoords[:, canvas.zax] = zpos
    texCoords[  :, canvas.zax] = zpos

    voxCoords  = image.worldToVox(texCoords)

    voxCoords[(voxCoords[:, 0] >= -0.5) & (voxCoords[:, 0] < 0), 0] = 0
    
    voxCoords[(voxCoords[:, 0] >= image.shape[0] - 1) &
              (voxCoords[:, 0] <= image.shape[0]), 0] = image.shape[0] - 1
    
    voxCoords[(voxCoords[:, 1] >= -0.5) & (voxCoords[:, 1] <= 0), 1] = 0
    voxCoords[(voxCoords[:, 1] >= image.shape[1] - 1) &
              (voxCoords[:, 1] <= image.shape[1]), 1] = image.shape[1] - 1
    
    voxCoords[(voxCoords[:, 2] >= -0.5) & (voxCoords[:, 2] <= 0), 2] = 0
    voxCoords[(voxCoords[:, 2] >= image.shape[2] - 1) &
              (voxCoords[:, 2] <= image.shape[2]), 2] = image.shape[2] - 1


    imageData        = glImageData.imageData
    texCoordXform    = glImageData.texCoordXform
    colourTexture    = glImageData.colourTexture
    nVertices        = voxCoords.shape[0]

    imageData = interp.interpn(map(np.arange, imageData.shape),
                               imageData,
                               voxCoords,
                               method=imageDisplay.interpolation,
                               bounds_error=False,
                               fill_value=np.array(0.0, dtype=np.float32))
    
    worldCoords = worldCoords.ravel('C')
    imageData   = imageData.ravel(  'C')

    if xform is not None: 
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glMultMatrixf(xform)

    gl.glTexEnvf(gl.GL_TEXTURE_ENV, gl.GL_TEXTURE_ENV_MODE, gl.GL_REPLACE)
    gl.glBindTexture(gl.GL_TEXTURE_1D, colourTexture)

    gl.glMatrixMode(gl.GL_TEXTURE)
    gl.glPushMatrix()
    gl.glMultMatrixf(texCoordXform)

    gl.glEnableClientState(gl.GL_TEXTURE_COORD_ARRAY)
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)

    gl.glVertexPointer(  3, gl.GL_FLOAT, 0, worldCoords)
    gl.glTexCoordPointer(1, gl.GL_FLOAT, 0, imageData)

    gl.glDrawArrays(gl.GL_QUADS, 0, nVertices)

    gl.glDisableClientState(gl.GL_TEXTURE_COORD_ARRAY)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)

    if xform is not None:
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPopMatrix()

    gl.glMatrixMode(gl.GL_TEXTURE)
    gl.glPopMatrix()
    
    
def drawScene(canvas):
    """Draws the currently selected slice (as specified by the ``z``
    value of the :attr:`pos` property) to the canvas."""

    canvas.glContext.SetCurrent(canvas)

    canvas._setViewport()

    # clear the canvas
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

    # enable transparency
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

    # disable interpolation
    gl.glShadeModel(gl.GL_FLAT)

    gl.glEnable(gl.GL_TEXTURE_1D)

    for image in canvas.imageList:

        log.debug('Drawing {} slice for image {}'.format(
            canvas.zax, image.name))

        drawSlice(canvas, image, canvas.pos.z)

    gl.glDisable(gl.GL_TEXTURE_1D)

    if canvas.showCursor:

        # A vertical line at xpos, and a horizontal line at ypos
        xverts = np.zeros((2, 3))
        yverts = np.zeros((2, 3))

        xmin, xmax = canvas.imageList.bounds.getRange(canvas.xax)
        ymin, ymax = canvas.imageList.bounds.getRange(canvas.yax)

        # add a little padding to the lines if they are
        # on the boundary, so they don't get cropped
        xverts[:, canvas.xax] = canvas.pos.x
        yverts[:, canvas.yax] = canvas.pos.y 

        xverts[:, canvas.yax] = [ymin, ymax]
        xverts[:, canvas.zax] =  canvas.pos.z + 1
        yverts[:, canvas.xax] = [xmin, xmax]
        yverts[:, canvas.zax] =  canvas.pos.z + 1

        gl.glBegin(gl.GL_LINES)
        gl.glColor3f(0, 1, 0)
        gl.glVertex3f(*xverts[0])
        gl.glVertex3f(*xverts[1])
        gl.glVertex3f(*yverts[0])
        gl.glVertex3f(*yverts[1])
        gl.glEnd()

    canvas.SwapBuffers()
