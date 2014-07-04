#!/usr/bin/env python
#
# slicecanvas.py - A wx.GLCanvas canvas which displays a single
# slice from a collection of 3D images.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""A :class:`wx.glcanvas.GLCanvas` canvas which displays a single
slice from a collection of 3D images.
"""

import logging

log = logging.getLogger(__name__)

import os.path     as op

import numpy       as np

import                wx
import wx.glcanvas as wxgl

import OpenGL.GL   as gl

# Under OS X, I don't think I can request an OpenGL 3.2 core profile
# using wx - I'm stuck with OpenGL 2.1 I'm using these ARB extensions
# for functionality which is standard in 3.2.
import OpenGL.GL.ARB.instanced_arrays as arbia
import OpenGL.GL.ARB.draw_instanced   as arbdi

import props

import fsl.data.fslimage          as fslimage
import fsl.fslview.gl.glimagedata as glimagedata


_vertex_shader_file   = op.join(op.dirname(__file__), 'vertex_shader.glsl')
"""Location of the GLSL vertex shader source code."""


_fragment_shader_file = op.join(op.dirname(__file__), 'fragment_shader.glsl')
"""Location of the GLSL fragment shader source code."""


class SliceCanvas(wxgl.GLCanvas, props.HasProperties):
    """A :class:`wx.glcanvas.GLCanvas` which may be used to display a single
    2D slice from a collection of 3D images (see
    :class:`fsl.data.fslimage.ImageList`).
    """

    pos = props.Point(ndims=3)
    """The currently displayed position. The ``pos.x`` and ``pos.y`` positions
    denote the position of a 'cursor', which is highlighted with green
    crosshairs. The ``pos.z`` position specifies the currently displayed
    slice. While the values of this point are in the image list world
    coordinates, the dimension ordering may not be the same as the image list
    dimension ordering. For this position, the x and y dimensions correspond
    to horizontal and vertical on the screen, and the z dimension to 'depth'.
    """


    zoom = props.Real(minval=1.0,
                      maxval=10.0, 
                      default=1.0,
                      clamped=True)
    """The image bounds are divided by this zoom
    factor to produce the display bounds.
    """

    
    displayBounds = props.Bounds(ndims=2)
    """The display bound x/y values specify the horizontal/vertical display
    range of the canvas, in world coordinates. This may be a larger area
    than the size of the displayed images, as it is adjusted to preserve the
    aspect ratio.
    """

    
    showCursor = props.Boolean(default=True)
    """If ``False``, the green crosshairs which show
    the current cursor location will not be drawn.
    """
 

    zax = props.Choice((0, 1, 2), ('X axis', 'Y axis', 'Z axis'))
    """The image axis to be used as the screen 'depth' axis."""

        
    def canvasToWorld(self, xpos, ypos):
        """Given pixel x/y coordinates on this canvas, translates them
        into the real world coordinates of the displayed slice.
        """

        realWidth    = self.displayBounds.xlen
        realHeight   = self.displayBounds.ylen
        canvasWidth  = float(self.GetClientSize().GetWidth())
        canvasHeight = float(self.GetClientSize().GetHeight()) 

        if realWidth    == 0 or \
           canvasWidth  == 0 or \
           realHeight   == 0 or \
           canvasHeight == 0:
            return 0 
        
        xpos = self.displayBounds.xlo + (xpos / canvasWidth)  * realWidth
        ypos = self.displayBounds.ylo + (ypos / canvasHeight) * realHeight

        return xpos, ypos


    def panDisplayBy(self, xoff, yoff):
        """Pans the canvas display by the given x/y offsets (specified in
        world coordinates).
        """
        
        bounds = self.displayBounds

        xmin, xmax, ymin, ymax = bounds[:]

        xmin = xmin + xoff
        xmax = xmax + xoff
        ymin = ymin + yoff
        ymax = ymax + yoff

        if xmin < bounds.getMin(0):
            xmin = bounds.getMin(0)
            xmax = xmin + bounds.getLen(0)
            
        elif xmax > bounds.getMax(0):
            xmax = bounds.getMax(0)
            xmin = xmax - bounds.getLen(0)
            
        if ymin < bounds.getMin(1):
            ymin = bounds.getMin(1)
            ymax = ymin + bounds.getLen(1)

        elif ymax > bounds.getMax(1):
            ymax = bounds.getMax(1)
            ymin = ymax - bounds.getLen(1) 

        self.displayBounds[:] = [xmin, xmax, ymin, ymax]


    def panDisplayToShow(self, xpos, ypos):
        """Pans the display so that the given x/y position (in world
        coordinates) is visible.
        """

        bounds = self.displayBounds

        if xpos >= bounds.xlo and xpos <= bounds.xhi and \
           ypos >= bounds.ylo and ypos <= bounds.yhi: return

        xoff = 0
        yoff = 0

        if   xpos <= bounds.xlo: xoff = xpos - bounds.xlo
        elif xpos >= bounds.xhi: xoff = xpos - bounds.xhi
        
        if   ypos <= bounds.ylo: yoff = ypos - bounds.ylo
        elif ypos >= bounds.yhi: yoff = ypos - bounds.yhi
        
        if xoff != 0 or yoff != 0:
            self.panDisplayBy(xoff, yoff)

        
    def __init__(self, parent, imageList, zax=0, glContext=None):
        """Creates a canvas object. The OpenGL data buffers for each image
        in the list are set up the first time that the canvas is
        displayed/drawn.
        
        :arg parent:    :mod:`wx` parent object
        
        :arg imageList: A :class:`fsl.data.fslimage.ImageList` object.
        
        :arg zax:       Image axis perpendicular to the plane to be displayed
                        (the 'depth' axis), default 0.

        :arg glContext: A :class:`wx.glcanvas.GLContext` object. If ``None``,
                        one is created.
        """

        if not isinstance(imageList, fslimage.ImageList):
            raise TypeError(
                'imageList must be a fsl.data.fslimage.ImageList instance')

        wxgl.GLCanvas.__init__(self, parent)
        props.HasProperties.__init__(self)

        # Use the provided shared GL
        # context, or create a new one
        if glContext is None: self.glContext = wxgl.GLContext(self)
        else:                 self.glContext = glContext

        self.imageList = imageList
        self.name      = '{}_{}'.format(self.__class__.__name__, id(self))

        # This flag is set by the _initGLData method
        # when it has finished initialising the OpenGL
        # shaders
        self.glReady = False

        # The image axis which maps to the 'depth' axis of this
        # canvas. The _zAxisChanged method also adds 'xax' and
        # 'yax' attributes to this SliceCanvas object.
        self.zax = zax
        self._zAxisChanged()
        self.addListener('zax', self.name, self._zAxisChanged)

        if len(self.imageList) > 0:
            
            self._imageBoundsChanged()
             
            self.pos.xyz = [
                self.imageList.location.getPos(self.xax),
                self.imageList.location.getPos(self.yax),
                self.imageList.location.getPos(self.zax)]

        # when any of the properties of this
        # canvas change, we need to redraw
        def refresh(*a): self.Refresh()
            
        self.addListener('pos',           self.name, refresh)
        self.addListener('showCursor',    self.name, refresh)
        self.addListener('displayBounds', self.name, refresh)
        self.addListener('zoom',
                         self.name,
                         lambda *a: self._updateDisplayBounds())

        # When the image list changes, refresh the
        # display, and update the display bounds
        self.imageList.addListener('images',
                                   self.name,
                                   self._imageListChanged)
        self.imageList.addListener('bounds',
                                   self.name,
                                   self._imageBoundsChanged)

        # the image list is probably going to outlive
        # this SliceCanvas object, so we do the right
        # thing and remove our listeners when we die
        def onDestroy(ev):
            self.imageList.removeListener('images', self.name)
            self.imageList.removeListener('bounds', self.name)
            ev.Skip()

        self.Bind(wx.EVT_WINDOW_DESTROY, onDestroy)

        # When the canvas is resized, we have to update
        # the display bounds to preserve the aspect ratio
        def onResize(ev):
            self._updateDisplayBounds()
            ev.Skip()
        self.Bind(wx.EVT_SIZE, onResize)

        # All the work is done by the draw method
        self.Bind(wx.EVT_PAINT, self._draw)

        
    def _zAxisChanged(self, *a):
        """Called when the :attr:`zax` property is changed. Calculates
        the corresponding X and Y axes, and saves them as attributes of
        the object. Also regenerates the GL index buffers for every
        image in the image list, as they are dependent upon how the
        image is being displayed.
        """

        log.debug('{}'.format(self.zax))
        
        dims = range(3)
        dims.pop(self.zax)
        self.xax = dims[0]
        self.yax = dims[1]

        if not self.glReady:
            return

        for image in self.imageList:

            try:   glData = image.getAttribute(self.name)

            # if this lookup fails, it means that the GL data
            # for this image has not yet been generated.
            except KeyError: continue
            
            glData.genIndexBuffers(self.xax, self.yax)
            
        self._imageBoundsChanged()
        
        # Reset the canvas position as, because the
        # z axis has been changed, the old coordinates
        # will be in the wrong dimension order
        self.pos.xyz = [self.imageList.location[self.xax],
                        self.imageList.location[self.yax],
                        self.imageList.location[self.zax]]
 
            
    def _imageListChanged(self, *a):
        """This method is called once by :meth:`_initGLData`, and then again
        every time an image is added or removed to/from the image list. For
        newly added images, it creates a
        :class:`~fsl.fslview.gl.glimagedata.GLImageData` object, which
        initialises the OpenGL data necessary to render the image, and then
        triggers a refresh.
        """

        # Create a GLImageData object for any new images,
        # and attach a listener to their display properties
        # so we know when to refresh the canvas.
        for image in self.imageList:
            try:
                glData = image.getAttribute(self.name)
                continue
                
            except KeyError:
                pass
                
            glData = glimagedata.GLImageData(image, self.xax, self.yax)
            image.setAttribute(self.name, glData)

            def refresh( *a): self.Refresh()

            image.display.addListener('enabled',      self.name, refresh)
            image.display.addListener('alpha',        self.name, refresh)
            image.display.addListener('displayRange', self.name, refresh)
            image.display.addListener('rangeClip',    self.name, refresh)
            image.display.addListener('samplingRate', self.name, refresh)
            image.display.addListener('cmap',         self.name, refresh)
            image.display.addListener('volume',       self.name, refresh)

            # remove all those listeners when
            # this SliceCanvas is destroyed
            def onDestroy(ev):
                image.display.removeListener('enabled',      self.name)
                image.display.removeListener('alpha',        self.name)
                image.display.removeListener('displayRange', self.name)
                image.display.removeListener('rangeClip',    self.name)
                image.display.removeListener('samplingRate', self.name)
                image.display.removeListener('cmap',         self.name)
                image.display.removeListener('volume',       self.name)
                ev.Skip()
                
            self.Bind(wx.EVT_WINDOW_DESTROY, onDestroy)

        self.Refresh()


    def _compileShaders(self):
        """Compiles and links the OpenGL GLSL vertex and fragment shader
        programs, and returns a reference to the resulting program. Raises
        an error if compilation/linking fails.

        I'm explicitly not using the PyOpenGL
        :func:`OpenGL.GL.shaders.compileProgram` function, because it attempts
        to validate the program after compilation, which fails due to texture
        data not being bound at the time of validation.
        """

        with open(_vertex_shader_file,   'rt') as f: vertShaderSrc = f.read()
        with open(_fragment_shader_file, 'rt') as f: fragShaderSrc = f.read()

        # vertex shader
        vertShader = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vertShader, vertShaderSrc)
        gl.glCompileShader(vertShader)
        vertResult = gl.glGetShaderiv(vertShader, gl.GL_COMPILE_STATUS)

        if vertResult != gl.GL_TRUE:
            raise RuntimeError('{}'.format(gl.glGetShaderInfoLog(vertShader)))

        # fragment shader
        fragShader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(fragShader, fragShaderSrc)
        gl.glCompileShader(fragShader)
        fragResult = gl.glGetShaderiv(fragShader, gl.GL_COMPILE_STATUS)

        if fragResult != gl.GL_TRUE:
            raise RuntimeError('{}'.format(gl.glGetShaderInfoLog(fragShader)))

        # link all of the shaders!
        program = gl.glCreateProgram()
        gl.glAttachShader(program, vertShader)
        gl.glAttachShader(program, fragShader)

        gl.glLinkProgram(program)

        gl.glDeleteShader(vertShader)
        gl.glDeleteShader(fragShader)

        linkResult = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)

        if linkResult != gl.GL_TRUE:
            raise RuntimeError('{}'.format(gl.glGetProgramInfoLog(program)))

        return program


    def _initGLData(self):
        """Compiles the vertex and fragment shader programs (see
        :meth:`_compileShaders`), and stores references to the
        shader variables as attributes of this :class:`SliceCanvas`
        object. This method is only called once, on the first draw.
        """

        # A bit hacky. We can only set the GL context (and create
        # the GL data) once something is actually displayed on the
        # screen. The _initGLData method is called (asynchronously)
        # by the draw() method if it sees that the glReady flag has
        # not yet been set. But draw() may be called mored than once
        # before _initGLData is called. Here, to prevent
        # _initGLData from running more than once, the first time
        # it is called it simply overrides itself with a dummy method.
        self._initGLData = lambda s: s
 
        self.glContext.SetCurrent(self)

        self.shaders = self._compileShaders()

        # Indices of all vertex/fragment shader parameters
        self.alphaPos         = gl.glGetUniformLocation(self.shaders, 'alpha')
        self.imageBufferPos   = gl.glGetUniformLocation(self.shaders,
                                                        'imageBuffer')
        self.voxToWorldMatPos = gl.glGetUniformLocation(self.shaders,
                                                        'voxToWorldMat')
        self.colourMapPos     = gl.glGetUniformLocation(self.shaders,
                                                        'colourMap')
        self.imageShapePos    = gl.glGetUniformLocation(self.shaders,
                                                        'imageShape') 
        self.subTexShapePos   = gl.glGetUniformLocation(self.shaders,
                                                        'subTexShape')
        self.subTexPadPos     = gl.glGetUniformLocation(self.shaders,
                                                        'subTexPad')
        self.normFactorPos    = gl.glGetUniformLocation(self.shaders,
                                                        'normFactor')
        self.normOffsetPos    = gl.glGetUniformLocation(self.shaders,
                                                        'normOffset') 
        self.displayMinPos    = gl.glGetUniformLocation(self.shaders,
                                                        'displayMin')
        self.displayMaxPos    = gl.glGetUniformLocation(self.shaders,
                                                        'displayMax') 
        self.signedPos        = gl.glGetUniformLocation(self.shaders,
                                                        'signed') 
        self.fullTexShapePos  = gl.glGetUniformLocation(self.shaders,
                                                        'fullTexShape')
        self.inVertexPos      = gl.glGetAttribLocation( self.shaders,
                                                        'inVertex')
        self.voxXPos          = gl.glGetAttribLocation( self.shaders, 'voxX')
        self.voxYPos          = gl.glGetAttribLocation( self.shaders, 'voxY')
        self.voxZPos          = gl.glGetAttribLocation( self.shaders, 'voxZ')

        # initialise data for the images that
        # are already in the image list 
        self._imageListChanged()

        self.glReady = True

        self.Refresh()


    def _imageBoundsChanged(self, *a):
        """Called when the image list bounds are changed.

        Updates the constraints on the :attr:`pos` property so it is
        limited to stay within a valid range, and then calls the
        :meth:`_updateDisplayBounds` method.
        """

        imgBounds = self.imageList.bounds

        self.pos.setMin(0, imgBounds.getLo(self.xax))
        self.pos.setMax(0, imgBounds.getHi(self.xax))
        self.pos.setMin(1, imgBounds.getLo(self.yax))
        self.pos.setMax(1, imgBounds.getHi(self.yax))
        self.pos.setMin(2, imgBounds.getLo(self.zax))
        self.pos.setMax(2, imgBounds.getHi(self.zax))

        self._updateDisplayBounds()
        

    def _applyZoom(self, xmin, xmax, ymin, ymax):
        """'Zooms' in to the given rectangle according to the
        current value of the zoom property. Returns a 4-tuple
        containing the updated bound values.
        """

        if self.zoom == 1.0:
            return (xmin, xmax, ymin, ymax)
        
        zoomFactor  = 1.0 / self.zoom

        xlen = xmax - xmin
        ylen = ymax - ymin

        newxlen = xlen * zoomFactor
        newylen = ylen * zoomFactor

        xmin = self.pos.x - 0.5 * newxlen
        xmax = self.pos.x + 0.5 * newxlen
        ymin = self.pos.y - 0.5 * newylen
        ymax = self.pos.y + 0.5 * newylen

        return (xmin, xmax, ymin, ymax)

        
    def _updateDisplayBounds(self, xmin=None, xmax=None, ymin=None, ymax=None):
        """Called on canvas resizes, image bound changes, and zoom changes.
        
        Calculates the bounding box, in world coordinates, to be displayed on
        the canvas. Stores this bounding box in the displayBounds property. If
        any of the parameters are not provided, the image list
        :attr:`fsl.data.fslimage.ImageList.bounds` are used.

        :arg xmin: Minimum x (horizontal) value to be in the display bounds.
        :arg xmax: Maximum x value to be in the display bounds.
        :arg ymin: Minimum y (vertical) value to be in the display bounds.
        :arg ymax: Maximum y value to be in the display bounds.
        """

        if xmin is None: xmin = self.imageList.bounds.getLo(self.xax)
        if xmax is None: xmax = self.imageList.bounds.getHi(self.xax)
        if ymin is None: ymin = self.imageList.bounds.getLo(self.yax)
        if ymax is None: ymax = self.imageList.bounds.getHi(self.yax)

        log.debug('Required display bounds: X: ({}, {}) Y: ({}, {})'.format(
            xmin, xmax, ymin, ymax))

        canvasWidth, canvasHeight = self.GetClientSize().Get()
        dispWidth                 = float(xmax - xmin)
        dispHeight                = float(ymax - ymin)

        if canvasWidth  == 0 or \
           canvasHeight == 0 or \
           dispWidth    == 0 or \
           dispHeight   == 0:
            self.displayBounds[:] = [xmin, xmax, ymin, ymax]
            return

        # These ratios are used to determine whether
        # we need to expand the display range to
        # preserve the image aspect ratio.
        dispRatio   =       dispWidth    / dispHeight
        canvasRatio = float(canvasWidth) / canvasHeight

        # the canvas is too wide - we need
        # to expand the display width, thus 
        # effectively shrinking the display
        # along the horizontal axis
        if canvasRatio > dispRatio:
            newDispWidth = canvasWidth * (dispHeight / canvasHeight)
            xmin         = xmin - 0.5 * (newDispWidth - dispWidth)
            xmax         = xmax + 0.5 * (newDispWidth - dispWidth)

        # the canvas is too high - we need
        # to expand the display height
        elif canvasRatio < dispRatio:
            newDispHeight = canvasHeight * (dispWidth / canvasWidth)
            ymin          = ymin - 0.5 * (newDispHeight - dispHeight)
            ymax          = ymax + 0.5 * (newDispHeight - dispHeight)

        self.displayBounds.setLimits(0, xmin, xmax)
        self.displayBounds.setLimits(1, ymin, ymax) 

        self.displayBounds[:] = self._applyZoom(xmin, xmax, ymin, ymax)

        
    def _setViewport(self,
                     xmin=None,
                     xmax=None,
                     ymin=None,
                     ymax=None,
                     zmin=None,
                     zmax=None):
        """Sets up the GL canvas size, viewport, and projection.

        This method is called by draw(), so does not need to be called
        manually. If any of the min/max parameters are not provided,
        they are taken from the :attr:`displayBounds` (x/y), and the
        image list :attr:`~fsl.data.fslimage.ImageList.bounds` (z).

        :arg xmin: Minimum x (horizontal) location
        :arg xmax: Maximum x location
        :arg ymin: Minimum y (vertical) location
        :arg ymax: Maximum y location
        :arg zmin: Minimum z (depth) location
        :arg zmax: Maximum z location 
        """
        
        if xmin is None: xmin = self.displayBounds.xlo
        if xmax is None: xmax = self.displayBounds.xhi
        if ymin is None: ymin = self.displayBounds.ylo
        if ymax is None: ymax = self.displayBounds.yhi
        if zmin is None: zmin = self.imageList.bounds.getLo(self.zax)
        if zmax is None: zmax = self.imageList.bounds.getHi(self.zax)

        # If there are no images to be displayed,
        # or no space to draw, do nothing
        width, height = self.GetClientSize().Get()
        
        if (len(self.imageList) == 0) or (width == 0) or (height == 0):
            return

        log.debug('Setting canvas bounds: '
                  'X {: 5.1f} - {: 5.1f},'
                  'Y {: 5.1f} - {: 5.1f}'.format(xmin, xmax, ymin, ymax))

        # set up 2D orthographic drawing
        gl.glViewport(0, 0, width, height)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        gl.glOrtho(xmin,        xmax,
                   ymin,        ymax,
                   zmin - 1000, zmax + 1000)
        # I don't know why the above +/-1000 is necessary :(
        # The '1000' is empirically arbitrary, but it seems
        # that I need to extend the depth clipping range
        # beyond the range of the data. This is despite the
        # fact that below, I'm actually translating the
        # displayed slice to Z=0! I don't understand OpenGL
        # sometimes. Most of the time.

        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()

        # Rotate world space so the displayed slice
        # is visible and correctly oriented
        # TODO There's got to be a more generic way
        # to perform this rotation. This will break
        # if I add functionality allowing the user
        # to specifty the x/y axes on initialisation.
        if self.zax == 0:
            gl.glRotatef(-90, 1, 0, 0)
            gl.glRotatef(-90, 0, 0, 1)
            
        elif self.zax == 1:
            gl.glRotatef(270, 1, 0, 0)

        # move the currently displayed slice to screen Z coord 0
        trans = [0, 0, 0]
        trans[self.zax] = -self.pos.z
        gl.glTranslatef(*trans)

        
    def _drawSlice(self, image, sliceno, xform=None):
        """Draws the specified slice from the specified image on the canvas.

        If ``xform`` is not provided, the
        :class:`~fsl.data.fslimage.Image` ``voxToWorldMat`` transformation
        matrix is used.

        :arg image:   The :class:`~fsl.data.fslimage.Image` object to draw.
        
        :arg sliceno: Voxel index of the slice to be drawn.
        
        :arg xform:   A 4*4 transformation matrix to be applied to the slice
                      data (or ``None`` to use the
                      :class:`~fsl.data.fslimage.Image` ``voxToWorldMat``
                      matrix).
        """

        # The GL data is stored as an attribute of the image,
        # and is created in the _imageListChanged method when
        # images are added to the image. If there's no data
        # here, ignore it; hopefully by the time _draw() is
        # called again, it will have been created.
        try:    glImageData = image.getAttribute(self.name)
        except: return
        
        imageDisplay = image.display

        # The number of voxels to be displayed along
        # each dimension is not necessarily equal to
        # the actual image shape, as the image may
        # be sampled at a lower resolution. The
        # GLImageData object keeps track of the
        # current image display resolution.
        xdim = glImageData.xdim
        ydim = glImageData.ydim
        zdim = glImageData.zdim
        
        # Don't draw the slice if this
        # image display is disabled
        if not imageDisplay.enabled: return

        # if the slice is out of range, don't draw it
        if sliceno < 0 or sliceno >= zdim: return

        # bind the current alpha value
        # and data range to the shader
        gl.glUniform1f(self.alphaPos,      imageDisplay.alpha)
        gl.glUniform1f(self.normFactorPos, glImageData.normFactor)
        gl.glUniform1f(self.normOffsetPos, glImageData.normOffset)
        gl.glUniform1f(self.displayMinPos, imageDisplay.displayRange.xlo)
        gl.glUniform1f(self.displayMaxPos, imageDisplay.displayRange.xhi)
        gl.glUniform1f(self.signedPos,     glImageData.signed)

        # and the image/texture shape buffers
        gl.glUniform3fv(self.fullTexShapePos, 1, glImageData.fullTexShape)
        gl.glUniform3fv(self.subTexShapePos,  1, glImageData.subTexShape)
        gl.glUniform3fv(self.subTexPadPos,    1, glImageData.subTexPad)
        gl.glUniform3fv(self.imageShapePos,   1, image.shape[:3])
        
        # bind the transformation matrix
        # to the shader variable
        if xform is None:
            xform = np.array(image.voxToWorldMat, dtype=np.float32)
        xform = xform.ravel('C')
        gl.glUniformMatrix4fv(self.voxToWorldMatPos, 1, False, xform)

        # Set up the colour texture
        gl.glActiveTexture(gl.GL_TEXTURE0) 
        gl.glBindTexture(gl.GL_TEXTURE_1D, glImageData.colourBuffer)
        gl.glUniform1i(self.colourMapPos, 0) 

        # Set up the image data texture
        gl.glActiveTexture(gl.GL_TEXTURE1) 
        gl.glBindTexture(gl.GL_TEXTURE_3D, glImageData.imageBuffer)
        gl.glUniform1i(self.imageBufferPos, 1)
        
        # voxel x/y/z coordinates
        voxOffs  = [0, 0, 0]
        voxSteps = [1, 1, 1]

        voxOffs[ self.zax] = sliceno
        voxSteps[self.yax] = xdim
        voxSteps[self.zax] = xdim * ydim
        for buf, pos, step, off in zip(
                (glImageData.voxXBuffer,
                 glImageData.voxYBuffer,
                 glImageData.voxZBuffer),
                (self.voxXPos,
                 self.voxYPos,
                 self.voxZPos),
                voxSteps,
                voxOffs):

            if off == 0: off = None
            else:        off = buf + (off * 2)
            
            buf.bind()
            gl.glVertexAttribPointer(
                pos,
                1,
                gl.GL_UNSIGNED_SHORT,
                gl.GL_FALSE,
                0,
                off)
            gl.glEnableVertexAttribArray(pos)
            arbia.glVertexAttribDivisorARB(pos, step)

        # The geometry buffer, which defines the geometry of a
        # single vertex (4 vertices, drawn as a triangle strip)
        glImageData.geomBuffer.bind()
        gl.glVertexAttribPointer(
            self.inVertexPos,
            3,
            gl.GL_FLOAT,
            gl.GL_FALSE,
            0,
            None)
        gl.glEnableVertexAttribArray(self.inVertexPos)
        arbia.glVertexAttribDivisorARB(self.inVertexPos, 0)

        # Draw all of the triangles!
        arbdi.glDrawArraysInstancedARB(
            gl.GL_TRIANGLE_STRIP, 0, 4, xdim * ydim)

        gl.glDisableVertexAttribArray(self.inVertexPos)
        gl.glDisableVertexAttribArray(self.voxXPos)
        gl.glDisableVertexAttribArray(self.voxYPos)
        gl.glDisableVertexAttribArray(self.voxZPos)

        
    def _draw(self, ev):
        """Draws the currently selected slice (as specified by the ``z``
        value of the :attr:`pos` property) to the canvas."""

        # image data has not been initialised.
        if not self.glReady:
            wx.CallAfter(self._initGLData)
            return

        self.glContext.SetCurrent(self)
        self._setViewport()

        # clear the canvas
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        # load the shaders
        gl.glUseProgram(self.shaders)

        # enable transparency
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        # disable interpolation
        gl.glShadeModel(gl.GL_FLAT)

        for image in self.imageList:

            log.debug('Drawing {} slice for image {}'.format(
                self.zax, image.name))

            zi = int(image.worldToVox(self.pos.z, self.zax))
            self._drawSlice(image, zi)

        gl.glUseProgram(0)

        if self.showCursor:

            # A vertical line at xpos, and a horizontal line at ypos
            xverts = np.zeros((2, 3))
            yverts = np.zeros((2, 3))

            xmin, xmax = self.imageList.bounds.getRange(self.xax)
            ymin, ymax = self.imageList.bounds.getRange(self.yax)

            # add a little padding to the lines if they are
            # on the boundary, so they don't get cropped
            xverts[:, self.xax] = self.pos.x
            yverts[:, self.yax] = self.pos.y 

            xverts[:, self.yax] = [ymin, ymax]
            xverts[:, self.zax] =  self.pos.z + 1
            yverts[:, self.xax] = [xmin, xmax]
            yverts[:, self.zax] =  self.pos.z + 1

            gl.glBegin(gl.GL_LINES)
            gl.glColor3f(0, 1, 0)
            gl.glVertex3f(*xverts[0])
            gl.glVertex3f(*xverts[1])
            gl.glVertex3f(*yverts[0])
            gl.glVertex3f(*yverts[1])
            gl.glEnd()

        self.SwapBuffers()