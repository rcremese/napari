from unittest.mock import patch

import numpy as np
import pytest
from qtpy.QtCore import QByteArray, QObject, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication, QColorDialog, QMainWindow

from napari._qt.utils import (
    QBYTE_FLAG,
    add_flash_animation,
    get_color,
    is_qbyte,
    qbytearray_to_str,
    qt_might_be_rich_text,
    qt_signals_blocked,
    str_to_qbytearray,
)
from napari.utils._proxies import PublicOnlyProxy


class Emitter(QObject):
    test_signal = Signal()

    def go(self):
        self.test_signal.emit()


def test_signal_blocker(qtbot):
    """make sure context manager signal blocker works"""

    obj = Emitter()

    # make sure signal works
    with qtbot.waitSignal(obj.test_signal):
        obj.go()

    # make sure blocker works
    with (
        qt_signals_blocked(obj),
        qtbot.assert_not_emitted(obj.test_signal, wait=500),
    ):
        obj.go()
    obj.deleteLater()


def test_is_qbyte_valid():
    assert is_qbyte(QBYTE_FLAG)
    assert is_qbyte(
        '!QBYTE_AAAA/wAAAAD9AAAAAgAAAAAAAAECAAACePwCAAAAAvsAAAAcAGwAYQB5AGUAcgAgAGMAbwBuAHQAcgBvAGwAcwEAAAAAAAABFwAAARcAAAEX+wAAABQAbABhAHkAZQByACAAbABpAHMAdAEAAAEXAAABYQAAALcA////AAAAAwAAAAAAAAAA/AEAAAAB+wAAAA4AYwBvAG4AcwBvAGwAZQAAAAAA/////wAAADIA////AAADPAAAAngAAAAEAAAABAAAAAgAAAAI/AAAAAA='
    )


def test_str_to_qbytearray_valid():
    assert isinstance(
        str_to_qbytearray(
            '!QBYTE_AAAA/wAAAAD9AAAAAgAAAAAAAAECAAACePwCAAAAAvsAAAAcAGwAYQB5AGUAcgAgAGMAbwBuAHQAcgBvAGwAcwEAAAAAAAABFwAAARcAAAEX+wAAABQAbABhAHkAZQByACAAbABpAHMAdAEAAAEXAAABYQAAALcA////AAAAAwAAAAAAAAAA/AEAAAAB+wAAAA4AYwBvAG4AcwBvAGwAZQAAAAAA/////wAAADIA////AAADPAAAAngAAAAEAAAABAAAAAgAAAAI/AAAAAA='
        ),
        QByteArray,
    )


def test_str_to_qbytearray_invalid():
    with pytest.raises(ValueError, match='Invalid QByte string.'):
        str_to_qbytearray('')

    with pytest.raises(ValueError, match='Invalid QByte string.'):
        str_to_qbytearray('FOOBAR')

    with pytest.raises(ValueError, match='Invalid QByte string.'):
        str_to_qbytearray(
            '_AAAA/wAAAAD9AAAAAgAAAAAAAAECAAACePwCAAAAAvsAAAAcAGwAYQB5AGUAcgAgAGMAbwBuAHQAcgBvAGwAcwEAAAAAAAABFwAAARcAAAEX+wAAABQAbABhAHkAZQByACAAbABpAHMAdAEAAAEXAAABYQAAALcA////AAAAAwAAAAAAAAAA/AEAAAAB+wAAAA4AYwBvAG4AcwBvAGwAZQAAAAAA/////wAAADIA////AAADPAAAAngAAAAEAAAABAAAAAgAAAAI/AAAAAA='
        )


def test_qbytearray_to_str(qtbot):
    widget = QMainWindow()
    qtbot.addWidget(widget)

    qbyte = widget.saveState()
    qbyte_string = qbytearray_to_str(qbyte)
    assert is_qbyte(qbyte_string)


def test_qbytearray_to_str_and_back(qtbot):
    widget = QMainWindow()
    qtbot.addWidget(widget)

    qbyte = widget.saveState()
    assert str_to_qbytearray(qbytearray_to_str(qbyte)) == qbyte


def test_add_flash_animation(qtbot):
    widget = QMainWindow()
    qtbot.addWidget(widget)
    assert widget.graphicsEffect() is None
    add_flash_animation(widget)
    assert widget.graphicsEffect() is not None
    assert hasattr(widget, '_flash_animation')
    qtbot.wait(350)
    assert widget.graphicsEffect() is None
    assert not hasattr(widget, '_flash_animation')


def test_qt_might_be_rich_text(qtbot):
    widget = QMainWindow()
    qtbot.addWidget(widget)
    assert qt_might_be_rich_text('<b>rich text</b>')
    assert not qt_might_be_rich_text('plain text')


def test_thread_proxy_guard(monkeypatch, qapp, single_threaded_executor):
    class X:
        a = 1

    monkeypatch.setenv('NAPARI_ENSURE_PLUGIN_MAIN_THREAD', 'True')

    x = X()
    x_proxy = PublicOnlyProxy(x)

    f = single_threaded_executor.submit(x.__setattr__, 'a', 2)
    f.result()
    assert x.a == 2

    f = single_threaded_executor.submit(x_proxy.__setattr__, 'a', 3)
    with pytest.raises(RuntimeError):
        f.result()
    assert x.a == 2


def test_get_color(qtbot):
    """Test the get_color utility function."""
    widget = QMainWindow()
    qtbot.addWidget(widget)

    with patch.object(QColorDialog, 'exec_') as mock:
        mock.return_value = QColorDialog.DialogCode.Accepted
        color = get_color(None, 'hex')
        assert isinstance(color, str), 'Expected string color'

    with patch.object(QColorDialog, 'exec_') as mock:
        mock.return_value = QColorDialog.DialogCode.Accepted
        color = get_color('#FF00FF', 'hex')
        assert isinstance(color, str), 'Expected string color'
        assert color == '#ff00ff', 'Expected color to be #FF00FF'

    with patch.object(QColorDialog, 'exec_') as mock:
        mock.return_value = QColorDialog.DialogCode.Accepted
        color = get_color(None, 'array')
        assert not isinstance(color, str), 'Expected array color'
        assert isinstance(color, np.ndarray), 'Expected numpy array color'

    with patch.object(QColorDialog, 'exec_') as mock:
        mock.return_value = QColorDialog.DialogCode.Accepted
        color = get_color(np.asarray([255, 0, 255]), 'array')
        assert not isinstance(color, str), 'Expected array color'
        assert isinstance(color, np.ndarray), 'Expected numpy array color'
        np.testing.assert_array_equal(color, np.asarray([1, 0, 1]))

    with patch.object(QColorDialog, 'exec_') as mock:
        mock.return_value = QColorDialog.DialogCode.Accepted
        color = get_color(None, 'qcolor')
        assert not isinstance(color, np.ndarray), 'Expected QColor color'
        assert isinstance(color, QColor), 'Expected QColor color'

    with patch.object(QColorDialog, 'exec_') as mock:
        mock.return_value = QColorDialog.DialogCode.Rejected
        color = get_color(None, 'qcolor')
        assert color is None, 'Expected None color'

    # close still open popup widgets
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QColorDialog):
            qtbot.addWidget(widget)
