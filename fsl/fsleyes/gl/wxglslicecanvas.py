#!/usr/bin/env python
#
# wxglslicecanvas.py - The WXGLSliceCanvas class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`WXGLSliceCanvas` class, which is a
:class:`.SliceCanvas` for use in a :mod:`wx` application.
"""


import wx
import wx.glcanvas    as wxgl

import slicecanvas    as slicecanvas
import fsl.fsleyes.gl as fslgl


class WXGLSliceCanvas(slicecanvas.SliceCanvas,
                      wxgl.GLCanvas,
                      fslgl.WXGLCanvasTarget):
    """The ``WXGLSliceCanvas`` is a :class:`.SliceCanvas`, a
    :class:`wx.glcanvas.GLCanvas` and a :class:`.WXGLCanvasTarget`. If you
    want to use a :class:`.SliceCanvas` in your :mod:`wx` application, then
    you should use a ``WXGLSliceCanvas``.

    .. note:: The ``WXGLSliceCanvas`` assumes the existence of the
              :meth:`.SliceCanvas._updateDisplayBounds` method.
    """

    def __init__(self, parent, overlayList, displayCtx, zax=0):
        """Create a ``WXGLSliceCanvas``. See :meth:`.SliceCanvas.__init__` for
        details on the arguments.
        """

        wxgl.GLCanvas          .__init__(self, parent)
        slicecanvas.SliceCanvas.__init__(self, overlayList, displayCtx, zax)
        fslgl.WXGLCanvasTarget .__init__(self)

        # When the canvas is resized, we have to update
        # the display bounds to preserve the aspect ratio
        def onResize(ev):
            self._updateDisplayBounds()
            ev.Skip()
        self.Bind(wx.EVT_SIZE, onResize)