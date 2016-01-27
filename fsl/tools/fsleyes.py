#!/usr/bin/env python
#
# fsleyes.py - Image viewer.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""*FSLeyes* - a 3D image viewer.

.. image:: images/fsleyes.png
   :scale: 50%
   :align: center

This module provides the front-end to *FSLeyes*, the FSL image viewer.  Nearly
all of the ``fsleyes`` functionality is located in the :mod:`fsl.fsleyes`
package. This module just parses command line arguments (via the
:mod:`.fsleyes_parseargs` module) and does some GUI bootstrapping necessities.


See the :mod:`~fsl.fsleyes` package documentation for more details on
``fsleyes``.
"""


import logging
import textwrap
import argparse

import fsl.fsleyes.fsleyes_parseargs as fsleyes_parseargs
import fsl.fsleyes.displaycontext    as displaycontext
import fsl.fsleyes.perspectives      as perspectives
import fsl.fsleyes.overlay           as fsloverlay
import fsl.utils.status              as status
import fsl.utils.async               as async


log = logging.getLogger(__name__)


def parseArgs(argv):
    """Parses the given ``fsleyes`` command line arguments. See the
    :mod:`.fsleyes_parseargs` module for details on the ``fsleyes`` command
    line interface.
    
    :arg argv: command line arguments for ``fsleyes``.
    """

    parser = argparse.ArgumentParser(
        add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # TODO Dynamically generate perspective list
    # in description. To do this, you will need
    # to make fsl.utils.settings work without a
    # wx.App (so we can retrieve the perspective
    # list before the GUI is created).
    name        = 'fsleyes'
    description = textwrap.dedent("""\
        FSLeyes - the FSL image viewer.
        
        Use the '--scene' option to load a saved perspective (e.g. 'default',
        'melodic', 'feat', 'ortho', or 'lightbox').
        
        If no '--scene' is specified, the previous layout is restored.
        """)

    # Options for configuring the scene are
    # managed by the fsleyes_parseargs module
    return fsleyes_parseargs.parseArgs(parser,
                                       argv,
                                       name,
                                       description)


def context(args):
    """Creates the ``fsleyes`` context.

    This function does a few things:

     1. Displays the ``fsleyes`` splash screen (see
        :class:`.FSLEyesSplash`). The splash screen is destroyed later on by
        the :func:`interface` function.

     2. Initialises OpenGL (see the :mod:`fsl.fsleyes.gl` package).

     3. Creates the :class:`.OverlayList` and the top level
        :class:`.DisplayContext`.

     4. Loads all of the overlays which were passed in on the command line.

    :arg args: Parsed command line arguments (see :func:`parseArgs`).

    :returns: a tuple containing:
                - the :class:`.OverlayList`
                - the master :class:`.DisplayContext`
                - the :class:`.FSLEyesSplash` frame
    """

    import fsl.fsleyes.splash as fslsplash

    # Create a splash screen, and use it
    # to initialise the OpenGL context
    
    # The splash screen is used as the parent of the dummy
    # canvas created by the gl.getWXGLContext function; the
    # splash screen frame is returned by this function, and
    # passed through to the interface function above, which
    # takes care of destroying it.
    frame = fslsplash.FSLEyesSplash(None)

    frame.CentreOnScreen()
    frame.Show()
    frame.Refresh()
    frame.Update()

    import props
    import fsl.fsleyes.gl as fslgl

    props.initGUI()
    
    # force the creation of a wx.glcanvas.GLContext object,
    # and initialise OpenGL version-specific module loads.
    fslgl.getWXGLContext(frame)
    fslgl.bootstrap(args.glversion)

    # Redirect status updates
    # to the splash frame
    status.setTarget(frame.SetStatus)

    # Create the overlay list (only one of these
    # ever exists) and the master DisplayContext.
    # A new DisplayContext instance will be
    # created for every new view that is opened
    # in the FSLEyesFrame (which is created in
    # the interface function, above), but all
    # child DisplayContext instances will be
    # linked to this master one.
    overlayList = fsloverlay.OverlayList()
    displayCtx  = displaycontext.DisplayContext(overlayList)

    # While the DisplayContext may refer to 
    # multiple overlay groups, we are currently
    # using just one, allowing the user to specify
    # a set of overlays for which their display
    # properties are 'locked'.
    lockGroup   = displaycontext.OverlayGroup(displayCtx, overlayList)
    displayCtx.overlayGroups.append(lockGroup)

    log.debug('Created overlay list and master DisplayContext ({})'.format(
        id(displayCtx)))
    
    # Load the images - the splash screen status will 
    # be updated with the currently loading overlay name
    fsleyes_parseargs.applyOverlayArgs(args, overlayList, displayCtx)  

    return overlayList, displayCtx, frame


def interface(parent, args, ctx):
    """Creates the ``fsleyes`` interface.

    This function does the following:

     1. Creates the :class:`.FSLEyesFrame` the top-level frame for ``fsleyes``.

     2. Configures the frame according to the command line arguments (e.g. 
        ortho or lightbox view).

     3. Destroys the splash screen that was created by the :func:`context`
        function.

    :arg parent: :mod:`wx` parent object.

    :arg args:   Parsed command line arguments, as returned by
                 :func:`parseArgs`.

    :arg ctx:    The :class:`.OverlayList`, :class:`.DisplayContext`, and
                 :class:`.FSLEyesSplash`, as created and returned by
                 :func:`context`.

    :returns: the :class:`.FSLEyesFrame` that was created.
    """

    import                      wx
    import fsl.fsleyes.frame as fsleyesframe
    import fsl.fsleyes.views as views

    overlayList, displayCtx, splashFrame = ctx

    # The scene argument can be:
    #
    #   - 'lightbox' or 'ortho', specifying a single view
    #      panel to display.
    # 
    #   - The name of a saved (or built-in) perspective
    # 
    #   - None, in which case the previous layout is restored
    scene = args.scene

    # If a scene or perspective has not been
    # specified, the default behaviour is to
    # restore the previous frame layout. 
    restore = scene is None

    status.update('Creating FSLeyes interface...')
    
    frame = fsleyesframe.FSLEyesFrame(
        parent, overlayList, displayCtx, restore, True)

    # Make sure the new frame is shown
    # before destroying the splash screen
    frame.Show(True)
    frame.Refresh()
    frame.Update()

    # Closing the splash screen immediately
    # can cause a crash under linux/GTK, so
    # we'll hide it now, and destroy it later.
    splashFrame.Hide()
    splashFrame.Refresh()
    splashFrame.Update()
    wx.CallLater(250, splashFrame.Close)

    # If a perspective has been specified,
    # we load the perspective
    if args.scene is not None:
        perspectives.loadPerspective(frame, args.scene)

    # The viewPanel is assumed to be a CanvasPanel 
    # (i.e. either OrthoPanel or LightBoxPanel)
    viewPanels = frame.getViewPanels()

    status.update('Setting up scene...')

    for viewPanel in viewPanels:

        if not isinstance(viewPanel, views.CanvasPanel):
            continue

        displayCtx = viewPanel.getDisplayContext()
        viewOpts   = viewPanel.getSceneOptions()

        fsleyes_parseargs.applySceneArgs(
            args, overlayList, displayCtx, viewOpts)

        def centre():
            if args.xcentre:
                viewPanel.getXCanvas().centreDisplayAt(*args.xcentre)
            if args.ycentre:
                viewPanel.getYCanvas().centreDisplayAt(*args.ycentre)
            if args.zcentre:
                viewPanel.getZCanvas().centreDisplayAt(*args.zcentre)

        if isinstance(viewPanel, views.OrthoPanel):
            async.idle(centre)
            
    return frame

    
#############################################
# See the fsl.tools package documentation for
# details on these module-level attributes
#############################################


FSL_TOOLNAME  = 'FSLeyes'
FSL_INTERFACE = interface
FSL_CONTEXT   = context
FSL_PARSEARGS = parseArgs