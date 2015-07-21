#!/usr/bin/env python
#
# layouts.py -
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#

import wx.lib.agw.aui as aui

import props

import fsl.utils.typedict  as td

import fsl.data.strings    as strings
import fsl.fslview.actions as actions

from fsl.fslview.profiles.orthoviewprofile import OrthoViewProfile
from fsl.fslview.profiles.orthoeditprofile import OrthoEditProfile

from fsl.fslview.views                     import OrthoPanel
from fsl.fslview.views                     import LightBoxPanel

from fsl.fslview.controls                  import OrthoToolBar
from fsl.fslview.controls                  import LightBoxToolBar
from fsl.fslview.controls                  import OverlayDisplayToolBar

from fsl.fslview.displaycontext            import Display
from fsl.fslview.displaycontext            import VolumeOpts
from fsl.fslview.displaycontext            import MaskOpts
from fsl.fslview.displaycontext            import VectorOpts
from fsl.fslview.displaycontext            import ModelOpts
from fsl.fslview.displaycontext            import LabelOpts

from fsl.fslview.displaycontext            import OrthoOpts
from fsl.fslview.displaycontext            import LightBoxOpts


def widget(labelCls, name, *args, **kwargs):

    label = strings.properties.get((labelCls, name), name)
    return props.Widget(name, label=label, *args, **kwargs)


########################################
# OrthoPanel related panels and toolbars
########################################


OrthoToolBarLayout = [
    actions.ActionButton(OrthoPanel,   'screenshot'),
    widget(              OrthoOpts,    'zoom', spin=False, showLimits=False),
    widget(              OrthoOpts,    'layout'),
    widget(              OrthoOpts,    'showXCanvas'),
    widget(              OrthoOpts,    'showYCanvas'),
    widget(              OrthoOpts,    'showZCanvas'),
    actions.ActionButton(OrthoToolBar, 'more')]


OrthoProfileToolBarViewLayout = [
    actions.ActionButton(OrthoViewProfile, 'resetZoom'),
    actions.ActionButton(OrthoViewProfile, 'centreCursor')]


# We cannot currently use the visibleWhen 
# feature, as toolbar labels won't be hidden.
OrthoProfileToolBarEditLayout = [
    props.Widget('mode'),
    actions.ActionButton(OrthoViewProfile, 'resetZoom'),
    actions.ActionButton(OrthoViewProfile, 'centreCursor'),
    actions.ActionButton(OrthoEditProfile, 'undo'),
    actions.ActionButton(OrthoEditProfile, 'redo'),
    actions.ActionButton(OrthoEditProfile, 'fillSelection'),
    actions.ActionButton(OrthoEditProfile, 'clearSelection'),
    actions.ActionButton(OrthoEditProfile, 'createMaskFromSelection'),
    actions.ActionButton(OrthoEditProfile, 'createROIFromSelection'),
    props.Widget('selectionCursorColour'),
    props.Widget('selectionOverlayColour'),    
    props.Widget('selectionSize',
                 enabledWhen=lambda p: p.mode in ['sel', 'desel']),
    props.Widget('selectionIs3D',
                 enabledWhen=lambda p: p.mode in ['sel', 'desel']),
    props.Widget('fillValue'),
    props.Widget('intensityThres',
                 enabledWhen=lambda p: p.mode == 'selint'),
    props.Widget('localFill',
                 enabledWhen=lambda p: p.mode == 'selint'),
    props.Widget('searchRadius',
                 enabledWhen=lambda p: p.mode == 'selint')]


#######################################
# LightBoxPanel control panels/toolbars
#######################################

LightBoxToolBarLayout = [
    actions.ActionButton(LightBoxPanel, 'screenshot'),
    widget(              LightBoxOpts, 'zax'),
    
    widget(LightBoxOpts, 'sliceSpacing', spin=False, showLimits=False),
    widget(LightBoxOpts, 'zrange',       spin=False, showLimits=False),
    widget(LightBoxOpts, 'zoom',         spin=False, showLimits=False),
    actions.ActionButton(LightBoxToolBar, 'more')]



##########################################
# Overlay display property panels/toolbars
##########################################


DisplayToolBarLayout = [
    widget(Display, 'name'),
    widget(Display, 'overlayType'),
    widget(Display, 'alpha',      spin=False, showLimits=False),
    widget(Display, 'brightness', spin=False, showLimits=False),
    widget(Display, 'contrast',   spin=False, showLimits=False)]


VolumeOptsToolBarLayout = [
    widget(VolumeOpts, 'cmap'),
    actions.ActionButton(OverlayDisplayToolBar, 'more')]


MaskOptsToolBarLayout = [
    widget(MaskOpts, 'colour'),
    actions.ActionButton(OverlayDisplayToolBar, 'more')]


VectorOptsToolBarLayout = [
    widget(VectorOpts, 'modulate'),
    widget(VectorOpts, 'modThreshold', showLimits=False, spin=False),
    actions.ActionButton(OverlayDisplayToolBar, 'more')]

ModelOptsToolBarLayout = [
    widget(ModelOpts, 'colour'),
    widget(ModelOpts, 'outline'),
    widget(ModelOpts, 'outlineWidth', showLimits=False, spin=False),
    actions.ActionButton(OverlayDisplayToolBar, 'more')]

LabelOptsToolBarLayout = [
    widget(LabelOpts, 'lut'),
    widget(LabelOpts, 'outline'),
    widget(LabelOpts, 'outlineWidth', showLimits=False, spin=False),
    actions.ActionButton(OverlayDisplayToolBar, 'more')]


layouts = td.TypeDict({

    ('OverlayDisplayToolBar', 'Display')        : DisplayToolBarLayout,
    ('OverlayDisplayToolBar', 'VolumeOpts')     : VolumeOptsToolBarLayout,
    ('OverlayDisplayToolBar', 'MaskOpts')       : MaskOptsToolBarLayout,
    ('OverlayDisplayToolBar', 'VectorOpts')     : VectorOptsToolBarLayout,
    ('OverlayDisplayToolBar', 'ModelOpts')      : ModelOptsToolBarLayout,
    ('OverlayDisplayToolBar', 'LabelOpts')      : LabelOptsToolBarLayout,

    'OrthoToolBar'    : OrthoToolBarLayout,
    'LightBoxToolBar' : LightBoxToolBarLayout,

    ('OrthoProfileToolBar', 'view') : OrthoProfileToolBarViewLayout,
    ('OrthoProfileToolBar', 'edit') : OrthoProfileToolBarEditLayout,
})


locations = td.TypeDict({
    'LocationPanel'       : aui.AUI_DOCK_BOTTOM,
    'OverlayListPanel'    : aui.AUI_DOCK_BOTTOM,
    'AtlasPanel'          : aui.AUI_DOCK_BOTTOM,
    'ImageDisplayToolBar' : aui.AUI_DOCK_TOP,
})
