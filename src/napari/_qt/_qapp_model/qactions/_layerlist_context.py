"""Qt 'Layer' menu Actions."""

from __future__ import annotations

import json
import pickle
from typing import Any

import numpy as np
import pint
from app_model.expressions import parse_expression
from app_model.types import Action
from qtpy.QtCore import QMimeData
from qtpy.QtWidgets import QApplication

from napari._app_model.constants import MenuGroup, MenuId
from napari._app_model.context import LayerListSelectionContextKeys as LLSCK
from napari.components import LayerList
from napari.layers import Layer
from napari.utils.notifications import show_warning
from napari.utils.translations import trans

__all__ = ('Q_LAYERLIST_CONTEXT_ACTIONS', 'is_valid_spatial_in_clipboard')


def _numpy_to_list(d: dict) -> dict:
    for k, v in list(d.items()):
        if isinstance(v, np.ndarray):
            d[k] = v.tolist()
    return d


class UnitsEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            obj = obj.tolist()
        if isinstance(obj, pint.Unit):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


def _set_data_in_clipboard(data: dict) -> None:
    data = _numpy_to_list(data)
    clip = QApplication.clipboard()
    if clip is None:
        show_warning('Cannot access clipboard')
        return

    d = json.dumps(data, cls=UnitsEncoder)
    p = pickle.dumps(data)
    mime_data = QMimeData()
    mime_data.setText(d)
    mime_data.setData('application/octet-stream', p)

    clip.setMimeData(mime_data)


def _copy_spatial_to_clipboard(layer: Layer) -> None:
    _set_data_in_clipboard(
        {
            'affine': layer.affine.affine_matrix,
            'rotate': layer.rotate,
            'scale': layer.scale,
            'shear': layer.shear,
            'translate': layer.translate,
            'units': layer.units,
        }
    )


DEFAULT_1D_VALUES = {
    'scale': 1.0,
    'translate': 0.0,
    'units': 'px',
}


def _copy_affine_to_clipboard(layer: Layer) -> None:
    _set_data_in_clipboard({'affine': layer.affine.affine_matrix})


def _copy_rotate_to_clipboard(layer: Layer) -> None:
    _set_data_in_clipboard({'rotate': layer.rotate})


def _copy_shear_to_clipboard(layer: Layer) -> None:
    _set_data_in_clipboard({'shear': layer.shear})


def _copy_scale_to_clipboard(layer: Layer) -> None:
    _set_data_in_clipboard({'scale': layer.scale})


def _copy_translate_to_clipboard(layer: Layer) -> None:
    _set_data_in_clipboard({'translate': layer.translate})


def _copy_units_to_clipboard(layer: Layer) -> None:
    _set_data_in_clipboard({'units': layer.units})


def _get_spatial_from_clipboard() -> dict | None:
    clip = QApplication.clipboard()
    if clip is None:
        return None

    mime_data = clip.mimeData()
    if mime_data is None:  # pragma: no cover
        # we should never get here, but just in case
        return None
    if mime_data.data('application/octet-stream'):
        return pickle.loads(mime_data.data('application/octet-stream'))  # type: ignore[arg-type]

    return json.loads(mime_data.text())


def _paste_spatial_from_clipboard(ll: LayerList) -> None:
    try:
        loaded = _get_spatial_from_clipboard()
    except (json.JSONDecodeError, pickle.UnpicklingError):
        show_warning('Cannot parse clipboard data')
        return
    if loaded is None:
        show_warning('Cannot access clipboard')
        return

    for layer in ll.selection:
        with layer._block_refresh():
            for key in loaded:
                loaded_attr_value = loaded[key]
                if key == 'units':
                    loaded_attr_value = (
                        (DEFAULT_1D_VALUES['units'],) * layer.ndim
                        + tuple(loaded_attr_value)
                    )[-layer.ndim :]
                elif isinstance(loaded_attr_value, list):
                    loaded_attr_value = np.array(loaded_attr_value)
                if key == 'shear':
                    elem_count = layer.ndim * (layer.ndim - 1) // 2
                    val_ = np.zeros(elem_count)
                    val_[-loaded_attr_value.size :] = loaded_attr_value[
                        -elem_count:
                    ]
                    loaded_attr_value = val_
                elif key == 'affine':
                    if loaded_attr_value.shape[0] >= layer.ndim + 1:
                        loaded_attr_value = loaded_attr_value[
                            -(layer.ndim + 1) :, -(layer.ndim + 1) :
                        ]
                    else:
                        val = np.eye(layer.ndim + 1)
                        val[
                            -loaded_attr_value.shape[0] :,
                            -loaded_attr_value.shape[1] :,
                        ] = loaded_attr_value
                        loaded_attr_value = val
                elif isinstance(loaded_attr_value, np.ndarray):
                    if loaded_attr_value.ndim == 1:
                        attr_len = len(loaded_attr_value)
                        if attr_len >= layer.ndim:
                            loaded_attr_value = loaded_attr_value[
                                -layer.ndim :
                            ]
                        else:
                            loaded_attr_value = np.array(
                                (DEFAULT_1D_VALUES[key],)
                                * (layer.ndim - attr_len)
                                + tuple(loaded_attr_value)
                            )
                    elif loaded_attr_value.ndim == 2:
                        if loaded_attr_value.shape[0] >= layer.ndim:
                            loaded_attr_value = loaded_attr_value[
                                -layer.ndim :, -layer.ndim :
                            ]
                        else:
                            val = np.eye(layer.ndim)
                            val[
                                -loaded_attr_value.shape[1] :,
                                -loaded_attr_value.shape[0] :,
                            ] = loaded_attr_value
                            loaded_attr_value = val

                setattr(layer, key, loaded_attr_value)

    for layer in ll.selection:
        layer.refresh(data_displayed=False)


def is_valid_spatial_in_clipboard() -> bool:
    try:
        loaded = _get_spatial_from_clipboard()
    except (json.JSONDecodeError, pickle.UnpicklingError):
        return False
    if not isinstance(loaded, dict):
        return False

    return set(loaded).issubset(
        {'affine', 'rotate', 'scale', 'shear', 'translate', 'units'}
    )


Q_LAYERLIST_CONTEXT_ACTIONS = [
    Action(
        id='napari.layer.copy_all_to_clipboard',
        title=trans._('Copy all to clipboard'),
        callback=_copy_spatial_to_clipboard,
        menus=[{'id': MenuId.LAYERS_CONTEXT_COPY_SPATIAL}],
        enablement=(LLSCK.num_selected_layers == 1),
    ),
    Action(
        id='napari.layer.copy_affine_to_clipboard',
        title=trans._('Copy affine to clipboard'),
        callback=_copy_affine_to_clipboard,
        menus=[{'id': MenuId.LAYERS_CONTEXT_COPY_SPATIAL}],
        enablement=(LLSCK.num_selected_layers == 1),
    ),
    Action(
        id='napari.layer.copy_rotate_to_clipboard',
        title=trans._('Copy rotate to clipboard'),
        callback=_copy_rotate_to_clipboard,
        menus=[{'id': MenuId.LAYERS_CONTEXT_COPY_SPATIAL}],
        enablement=(LLSCK.num_selected_layers == 1),
    ),
    Action(
        id='napari.layer.copy_scale_to_clipboard',
        title=trans._('Copy scale to clipboard'),
        callback=_copy_scale_to_clipboard,
        menus=[{'id': MenuId.LAYERS_CONTEXT_COPY_SPATIAL}],
        enablement=(LLSCK.num_selected_layers == 1),
    ),
    Action(
        id='napari.layer.copy_shear_to_clipboard',
        title=trans._('Copy shear to clipboard'),
        callback=_copy_shear_to_clipboard,
        menus=[{'id': MenuId.LAYERS_CONTEXT_COPY_SPATIAL}],
        enablement=(LLSCK.num_selected_layers == 1),
    ),
    Action(
        id='napari.layer.copy_translate_to_clipboard',
        title=trans._('Copy translate to clipboard'),
        callback=_copy_translate_to_clipboard,
        menus=[{'id': MenuId.LAYERS_CONTEXT_COPY_SPATIAL}],
        enablement=(LLSCK.num_selected_layers == 1),
    ),
    Action(
        id='napari.layer.copy_units_to_clipboard',
        title=trans._('Copy units to clipboard'),
        callback=_copy_units_to_clipboard,
        menus=[{'id': MenuId.LAYERS_CONTEXT_COPY_SPATIAL}],
        enablement=(LLSCK.num_selected_layers == 1),
    ),
    Action(
        id='napari.layer.paste_spatial_from_clipboard',
        title=trans._('Apply scale/transforms from Clipboard'),
        callback=_paste_spatial_from_clipboard,
        menus=[
            {
                'id': MenuId.LAYERLIST_CONTEXT,
                'group': MenuGroup.LAYERLIST_CONTEXT.COPY_SPATIAL,
            }
        ],
        enablement=parse_expression('valid_spatial_json_clipboard'),
    ),
]
