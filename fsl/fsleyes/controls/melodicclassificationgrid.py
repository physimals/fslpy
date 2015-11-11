#!/usr/bin/env python
#
# melodicclassificationgrid.py - the ComponentGrid and LabelGrid classes.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`ComponentGrid` and :class:`LabelGrid`
classes, which are used by the :class:`.MelodicClassificationPanel`.
"""


import logging

import wx

import pwidgets.widgetgrid        as widgetgrid
import pwidgets.texttag           as texttag

import fsl.fsleyes.panel          as fslpanel
import fsl.fsleyes.colourmaps     as fslcm
import fsl.fsleyes.displaycontext as fsldisplay
import fsl.data.melodicimage      as fslmelimage
import fsl.data.strings           as strings


log = logging.getLogger(__name__)


class ComponentGrid(fslpanel.FSLEyesPanel):
    """The ``ComponentGrid`` uses a :class:`.WidgetGrid`, and a set of
    :class:`.TextTagPanel` widgets, to display the component classifications
    stored in the :class:`.MelodicClassification` object that is associated
    with the currently selected overlay (if this overlay is a
    :class:`.MelodicImage`.

    The grid contains one row for each component, and a ``TextTagPanel`` is
    used to display the labels associated with each component. Each
    ``TextTagPanel`` allows the user to add and remove labels to/from the
    corresponding component.
    """

    
    def __init__(self, parent, overlayList, displayCtx, lut):
        """Create a ``ComponentGrid``.

        :arg parent:      The ``wx`` parent object.
        :arg overlayList: The :class:`.OverlayList`.
        :arg displayCtx:  The :class:`.DisplayContext`.
        :arg lut:         The :class:`.LookupTable` instance used to colour
                          each label tag.
        """
        
        fslpanel.FSLEyesPanel.__init__(self, parent, overlayList, displayCtx)

        self.__lut  = lut
        self.__grid = widgetgrid.WidgetGrid(
            self,
            style=(wx.VSCROLL                    |
                   widgetgrid.WG_SELECTABLE_ROWS |
                   widgetgrid.WG_KEY_NAVIGATION))

        self.__grid.ShowRowLabels(False)
        self.__grid.ShowColLabels(True)

        self.__sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.__sizer.Add(self.__grid, flag=wx.EXPAND, proportion=1)
        
        self.SetSizer(self.__sizer)
        
        self.__grid.Bind(widgetgrid.EVT_WG_SELECT, self.__onGridSelect)

        lut        .addListener('labels', self._name, self.__lutChanged)
        displayCtx .addListener('selectedOverlay',
                                self._name,
                                self.__selectedOverlayChanged)
        overlayList.addListener('overlays',
                                self._name,
                                self.__selectedOverlayChanged)

        self.__overlay = None
        self.__selectedOverlayChanged()

        
    def destroy(self):
        """Must be called when this ``ComponentGrid`` is no longer needed.
        De-registers various property listeners, and calls
        :meth:`.FSLEyesPanel.destroy`.
        """
        
        self._displayCtx .removeListener('selectedOverlay', self._name)
        self._overlayList.removeListener('overlays',        self._name)
        self.__lut       .removeListener('labels',          self._name)
        self.__deregisterCurrentOverlay()
        
        self.__lut = None

        fslpanel.FSLEyesPanel.destroy(self)


    def __deregisterCurrentOverlay(self):
        """Called when the selected overlay changes. De-registers listeners
        associated with the previously selected overlay, if necessary.
        """

        if self.__overlay is None:
            return

        overlay        = self.__overlay
        self.__overlay = None
        
        melclass = overlay.getICClassification()
        melclass.removeListener('labels', self._name)
            
        try:
            display = self._displayCtx.getDisplay(overlay)
            opts    = display.getDisplayOpts()
            opts   .removeListener('volume',      self._name)
            display.removeListener('overlayType', self._name)
            
        except fsldisplay.InvalidOverlayError:
            pass

        
    def __selectedOverlayChanged(self, *a):
        """Called when the :attr:`.DisplayContext.selectedOverlay` changes. If
        the overlay is a :class:`.MelodicImage`, the :class:`.WidgetGrid` is
        re-populated to display the component-label mappings contained in the
        associated :class:`.MelodicClassification` instance.
        """

        self.__deregisterCurrentOverlay()
        self.__grid.ClearGrid()

        overlay = self._displayCtx.getSelectedOverlay()

        if not isinstance(overlay, fslmelimage.MelodicImage):
            return

        self.__overlay = overlay
        display        = self._displayCtx.getDisplay(overlay)
        opts           = display.getDisplayOpts()
        melclass       = overlay.getICClassification()
        ncomps         = overlay.numComponents()
        
        self.__grid.SetGridSize(ncomps, 2, growCols=[1])

        self.__grid.SetColLabel(0, strings.labels[self, 'componentColumn'])
        self.__grid.SetColLabel(1, strings.labels[self, 'labelColumn'])

        opts    .addListener('volume', self._name, self.__volumeChanged)
        melclass.addListener('labels', self._name, self.__labelsChanged)
        display .addListener('overlayType',
                             self._name,
                             self.__selectedOverlayChanged)
        
        self.__recreateTags()
        self.__volumeChanged()

        
    def __recreateTags(self):
        """Re-creates a :class:`.TextTagPanel` for every component in the
        :class:`.MelodicImage`.
        """

        overlay  = self.__overlay
        numComps = overlay.numComponents()

        for i in range(numComps):

            tags = texttag.TextTagPanel(self.__grid,
                                        style=(texttag.TTP_ALLOW_NEW_TAGS |
                                               texttag.TTP_ADD_NEW_TAGS   |
                                               texttag.TTP_NO_DUPLICATES  |
                                               texttag.TTP_KEYBOARD_NAV))

            # Store the component number on the tag
            # panel, so we know which component we
            # are dealing with in the __onTagAdded
            # and __onTagRemoved methods.
            tags._melodicComponent = i

            self.__grid.SetText(  i, 0, str(i))
            self.__grid.SetWidget(i, 1, tags)

            tags.Bind(texttag.EVT_TTP_TAG_ADDED,   self.__onTagAdded)
            tags.Bind(texttag.EVT_TTP_TAG_REMOVED, self.__onTagRemoved)

        self.__refreshTags()

        self.Layout()

        
    def __refreshTags(self):
        """Re-generates the tags on every :class:`.TextTagPanel` in the grid.
        """ 
        
        overlay  = self.__overlay
        melclass = overlay.getICClassification()
        numComps = overlay.numComponents() 
        lut      = self.__lut

        labels  = [l.name()   for l in lut.labels]
        colours = [l.colour() for l in lut.labels]

        # Compile lists of all the existing
        # labels, and the colours for each one
        for i in range(numComps):

            for label in melclass.getLabels(i):
                if label in labels:
                    continue

                labels .append(label)
                colours.append(fslcm.randomBrightColour())
        
        for i in range(len(colours)):
            colours[i] = [int(round(c * 255)) for c in colours[i]] 

        for row in range(numComps):
            tags = self.__grid.GetWidget(row, 1)

            tags.ClearTags()
            tags.SetOptions(labels, colours)

            for label in melclass.getLabels(row):
                tags.AddTag(label)


    def __onTagAdded(self, ev):
        """Called when a tag is added to a :class:`.TextTagPanel`. Adds the
        corresponding component-label mapping to the
        :class:`.MelodicClassification` instance.
        """

        tags      = ev.GetEventObject()
        label     = ev.tag
        component = tags._melodicComponent
        overlay   = self.__overlay
        lut       = self.__lut 
        melclass  = overlay.getICClassification()

        # Add the new label to the melodic component
        melclass.disableListener('labels', self._name)
        melclass.addLabel(component, label)

        # If the tag panel previously just contained
        # the 'Unknown' tag, remove that tag
        if tags.TagCount() == 2 and tags.HasTag('unknown'):
            melclass.removeLabel(component, 'unknown')
            tags.RemoveTag('unknown')

        melclass.enableListener('labels', self._name)

        # If the newly added tag is not in
        # the lookup table, add it in
        if lut.getByName(label) is None:
            colour = tags.GetTagColour(label)
            colour = [c / 255.0 for c in colour]

            lut.disableListener('labels', self._name)
            lut.new(name=label, colour=colour)
            lut.enableListener('labels', self._name)

        self.__grid.FitInside()

        
    def __onTagRemoved(self, ev):
        """Called when a tag is removed from a :class:`.TextTagPanel`.
        Removes the corresponding component-label mapping from the
        :class:`.MelodicClassification` instance.
        """ 
        
        tags      = ev.GetEventObject()
        label     = ev.tag
        component = tags._melodicComponent
        overlay   = self.__overlay
        melclass  = overlay.getICClassification()

        # Remove the label from
        # the melodic component
        melclass.disableListener('labels', self._name)
        melclass.removeLabel(component, label)
        melclass.enableListener('labels', self._name)
 
        # If the tag panel now has no tags,
        # add the 'Unknown' tag back in.
        if tags.TagCount() == 0:
            tags.AddTag('Unknown') 

        self.__grid.FitInside()


    def __onGridSelect(self, ev):
        """Called when a row is selected on the :class:`.WidgetGrid`. Makes
        sure that the 'new tag' control in the corresponding
        :class:`.TextTagPanel` is focused.
        """

        component = ev.row
        opts      = self._displayCtx.getOpts(self.__overlay)

        opts.disableListener('volume', self._name)
        opts.volume = component
        opts.enableListener('volume', self._name)

        tags = self.__grid.GetWidget(ev.row, 1)
        tags.FocusNewTagCtrl()


    def __volumeChanged(self, *a):
        """Called when the :attr:`.ImageOpts.volume` property changes. Selects
        the corresponding row in the :class:`.WidgetGrid`.
        """

        # Only change the row if we are
        # currently visible, otherwise
        # this will screw up the focus.
        if not self.IsShown():
            return

        grid = self.__grid
        opts = self._displayCtx.getOpts(self.__overlay)
        tags = grid.GetWidget(opts.volume, 1)
 
        grid.SetSelection(opts.volume, -1)
        tags.FocusNewTagCtrl()


    def __labelsChanged(self, *a):
        """Called when the :attr:`.MelodicClassification.labels` change.
        Re-generates the tags shown on every :class:`.TextTagPanel`.
        """
        self.__refreshTags()


    def __lutChanged(self, *a):
        """Called when the :attr:`.LookupTable.labels` change.
        Re-generates the tags shown on every :class:`.TextTagPanel`.
        """ 
        self.__refreshTags()


class LabelGrid(fslpanel.FSLEyesPanel):
    """The ``LabelGrid`` class is the inverse of the :class:`ComponentGrid`.
    It uses a :class:`.WidgetGrid` to display the label-component mappings
    present on the :class:`.MelodicClassification` instance associated with
    the currently selected overlay (if this overlay is a
    :class:`.MelodicImage`.

    The grid contains one row for each label, and a :class:`.TextTagPanel` is
    used to display the components associated with each label. Each
    ``TextTagPanel`` allows the user to add and remove components to/from the
    corresponding label.
    """

    
    def __init__(self, parent, overlayList, displayCtx, lut):
        """Create a ``LabelGrid``.

        :arg parent:      The ``wx`` parent object.
        :arg overlayList: The :class:`.OverlayList`.
        :arg displayCtx:  The :class:`.DisplayContext`.
        :arg lut:         The :class:`.LookupTable` to be used to colour
                          component tags.
        """
        
        fslpanel.FSLEyesPanel.__init__(self, parent, overlayList, displayCtx)

        self.__lut  = lut
        self.__grid = widgetgrid.WidgetGrid(
            self,
            style=(wx.VSCROLL                    |
                   widgetgrid.WG_SELECTABLE_ROWS |
                   widgetgrid.WG_KEY_NAVIGATION))

        self.__grid.ShowRowLabels(False)
        self.__grid.ShowColLabels(True)

        self.__sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.__sizer.Add(self.__grid, flag=wx.EXPAND, proportion=1)
        
        self.SetSizer(self.__sizer)

        self.__grid.Bind(widgetgrid.EVT_WG_SELECT, self.__onGridSelect)

        lut        .addListener('labels', self._name, self.__lutChanged)
        displayCtx .addListener('selectedOverlay',
                                self._name,
                                self.__selectedOverlayChanged)
        overlayList.addListener('overlays',
                                self._name,
                                self.__selectedOverlayChanged)

        self.__overlay     = None
        self.__recreateGrid()
        self.__selectedOverlayChanged()

        
    def destroy(self):
        """Must be called when this ``LabelGrid`` is no longer needed.
        De-registers various property listeners, and calls
        :meth:`.FSLEyesPanel.destroy`.
        """
        
        self._displayCtx .removeListener('selectedOverlay', self._name)
        self._overlayList.removeListener('overlays',        self._name)
        self.__lut       .removeListener('labels',          self._name)
        self.__deregisterCurrentOverlay()
        
        self.__lut = None

        fslpanel.FSLEyesPanel.destroy(self)

        
    def __deregisterCurrentOverlay(self):
        """Called when the selected overlay changes. De-registers property
        listeners associated with the previously selected overlay, if
        necessary.
        """

        if self.__overlay is None:
            return

        overlay        = self.__overlay
        self.__overlay = None
        
        melclass = overlay.getICClassification()
        melclass.removeListener('labels', self._name)


    def __selectedOverlayChanged(self, *a):
        """Called when the :attr:`.DisplayContext.selectedOverlay` changes.
        If the overlay is a :class:`.MelodicImage`, a listener is registered
        with its :class:`.MelodicClassification`, and its component-label
        mappings displayed on the :class:`.WidgetGrid`.
        """

        self.__deregisterCurrentOverlay()

        overlay = self._displayCtx.getSelectedOverlay()

        if not isinstance(overlay, fslmelimage.MelodicImage):
            return

        self.__overlay = overlay
        melclass       = overlay.getICClassification()

        melclass.addListener('labels', self._name, self.__labelsChanged)

        self.__refreshTags()


    def __recreateGrid(self):
        """Clears the :class:`.WidgetGrid`, and re-creates
        a :class:`.TextTagPanel` for every available melodic classification
        label.
        """

        grid   = self.__grid
        lut    = self.__lut
        labels = lut.labels
        
        grid.ClearGrid()

        grid.SetGridSize(len(labels), 2, growCols=[1])

        grid.SetColLabel(0, strings.labels[self, 'labelColumn'])
        grid.SetColLabel(1, strings.labels[self, 'componentColumn'])

        for i, label in enumerate(labels):
            tags = texttag.TextTagPanel(self.__grid,
                                        style=(texttag.TTP_NO_DUPLICATES |
                                               texttag.TTP_KEYBOARD_NAV))

            tags._label = label.name()

            self.__grid.SetText(  i, 0, label.name())
            self.__grid.SetWidget(i, 1, tags)
            
            tags.Bind(texttag.EVT_TTP_TAG_ADDED,   self.__onTagAdded)
            tags.Bind(texttag.EVT_TTP_TAG_REMOVED, self.__onTagRemoved)
            tags.Bind(texttag.EVT_TTP_TAG_SELECT,  self.__onTagSelect)


    def __refreshTags(self):
        """Re-populates the label-component mappings shown on the
        :class:`.TextTagPanel` widgets in the :class:`.WidgetGrid`.
        """

        lut      = self.__lut
        grid     = self.__grid
        overlay  = self.__overlay
        numComps = overlay.numComponents()
        melclass = overlay.getICClassification()

        for i, label in enumerate(lut.labels):

            tags  = grid.GetWidget(i, 1)
            comps = melclass.getComponents(label.name())
            
            tags.ClearTags()

            tags.SetOptions(map(str, range(numComps)))

            for comp in comps:

                colour = label.colour()
                colour = [int(round(c  * 255.0)) for c in colour]
                tags.AddTag(str(comp), colour)

        self.__grid.Layout()

                
    def __onTagAdded(self, ev):
        """Called when a tag is added to a :class:`.TextTagPanel`. Adds
        the corresponding label-component mapping to the
        :class:`.MelodicClassification` instance.
        """ 

        tags     = ev.GetEventObject()
        overlay  = self.__overlay
        melclass = overlay.getICClassification()
        comp     = int(ev.tag)

        melclass.disableListener('labels', self._name)

        # If this component now has two labels, and
        # the other label is 'Unknown', remove the
        # 'Unknown' label.
        if len(melclass.getLabels(comp)) == 1 and \
           melclass.hasLabel(comp, 'Unknown'):
            melclass.removeLabel(comp, 'Unknown')
        
        melclass.addComponent(tags._label, comp)

        melclass.enableListener('labels', self._name)
        self.__refreshTags()

    
    def __onTagRemoved(self, ev):
        """Called when a tag is removed from a :class:`.TextTagPanel`. Removes
        the corresponding label-component mapping from the
        :class:`.MelodicClassification` instance.
        """
        
        tags     = ev.GetEventObject()
        overlay  = self.__overlay
        melclass = overlay.getICClassification()
        comp     = int(ev.tag)

        melclass.disableListener('labels', self._name)
        
        melclass.removeComponent(tags._label, comp)

        # If the component has no more labels,
        # give it an 'Unknown' label
        if len(melclass.getLabels(comp)) == 0:
            melclass.addLabel(comp, 'Unknown')
            
        melclass.enableListener('labels', self._name)
        self.__refreshTags()


    def __onGridSelect(self, ev):
        """Called when a row is selected in the :class:`.WidgetGrid`. Makes
        sure that  the first tag in the :class:`.TextTagPanel` has the focus.
        """

        tags = self.__grid.GetWidget(ev.row, 1)
        tags.FocusNewTagCtrl()


    def __onTagSelect(self, ev):
        """Called when a tag from a :class:`.TextTagPanel` is selected.
        Changes the current :attr:`.ImageOpts.volume` to the component
        corresponding to the selected tag.
        """
        
        tag         = int(ev.tag)
        overlay     = self.__overlay
        opts        = self._displayCtx.getOpts(overlay)
        opts.volume = tag
       

    def __lutChanged(self, *a):
        """Called when the :attr:`LookupTable.labels` change. Re-creates and
        re-populates the :class:`.WidgetGrid`.
        """
        log.debug('Lookup table changed - re-creating label grid')
        self.__recreateGrid()
        self.__refreshTags()

        
    def __labelsChanged(self, *a):
        """Called when the :attr:`.MelodicClassification.labels` change.
        Re-populates the :class:`.WidgetGrid`.
        """
        log.debug('Melodic classification changed - refreshing tags')
        self.__refreshTags()
