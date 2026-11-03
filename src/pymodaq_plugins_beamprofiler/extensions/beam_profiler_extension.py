import numpy as np
import pyqtgraph as pg
from qtpy import QtWidgets, QtGui
from qtpy.QtCore import QSettings, QByteArray, Qt, QRect, QRectF
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui import utils as gutils
from pymodaq_gui.plotting.data_viewers.viewer2D import Viewer2D
from pymodaq_gui.utils.widgets.lcd import LCD
from pymodaq.control_modules.daq_viewer import DAQ_Viewer
from pymodaq_utils.config import GlobalConfig, get_set_config_dir
from pymodaq_utils.logger import set_logger, get_module_name
from pymodaq.utils.custom_ext import CustomExt
from pymodaq.utils.managers.modules import ModuleType
from pymodaq_data.data import DataRaw
import laserbeamsize as lbs

from pymodaq.utils.data import DataFromPlugins # should be something else

logger = set_logger(get_module_name(__file__))

config = GlobalConfig()

EXTENSION_NAME = 'BeamProfiler'
CLASS_NAME = 'BeamProfilerExtension'


#>>> can be dropped as soon as the corresponding PR is in the main branch
from typing import List
import numpy as np
from qtpy.QtCore import QObject
from pymodaq_gui.plotting.data_viewers.viewer0D import Viewer0D

class MyLCD(QObject):

    def __init__(self, parent: QtWidgets.QWidget, **kwargs):
        super().__init__()
        self.Nvals = None
        self.labels = None
        self.parent = parent
        self.viewer0D = None
        self.digits = 3
        self.setupui(**kwargs)

    def setvalues(self, values: List[np.ndarray]):
        """
        display values on lcds
        Parameters
        ----------
        values: list of 0D ndarray

        Returns
        -------

        """
        while len(values) < self.Nvals:
            values.append(np.array([0.]))
        if len(values) > self.Nvals:
            values = values[:self.Nvals]
        vals = []
        for ind, val in enumerate(values):
            self.lcds[ind].display(val[0])
            vals.append(val)
        self.viewer0D.show_data(DataRaw(name='LCD', data=values[2:4]))

    def setupui(self, **kwargs):
        if 'digits' in kwargs:
            self.digits = kwargs['digits']
        if 'Nvals' in kwargs:
            self.Nvals = kwargs['Nvals']
        else:
            self.Nvals = 1
        if 'labels' in kwargs:
            self.labels = kwargs['labels']
        else:
            self.labels = ['CH{:d}'.format(ind) for ind in range(self.Nvals)]

        while len(self.labels) < self.Nvals:
            self.labels.append('')

        vlayout = QtWidgets.QVBoxLayout()
        self.hsplitter = QtWidgets.QSplitter()
        vlayout.addWidget(self.hsplitter)
        self.parent.setLayout(vlayout)
        form = QtWidgets.QWidget()
        self.viewer0D = Viewer0D(form)
        self.viewer0D.labels = self.labels

        vlayout = QtWidgets.QVBoxLayout()

        lcd_layouts = []
        labels = []
        self.lcds = []

        for ind in range(self.Nvals):
            lcd_layouts.append(QtWidgets.QVBoxLayout())
            labels.append(QtWidgets.QLabel(self.labels[ind]))
            labels[-1].setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                     QtWidgets.QSizePolicy.Maximum)
            self.lcds.append(QtWidgets.QLCDNumber())
            self.lcds[-1].setDigitCount(self.digits)
            lcd_layouts[-1].addWidget(labels[-1])
            lcd_layouts[-1].addWidget(self.lcds[-1])
            vlayout.addLayout(lcd_layouts[-1])

            if ind != self.Nvals - 1:
                hFrame = QtWidgets.QFrame()
                hFrame.setFrameShape(QtWidgets.QFrame.HLine)
                vlayout.addWidget(hFrame)

        lcd_widget = QtWidgets.QWidget()
        lcd_widget.setLayout(vlayout)
        self.hsplitter.addWidget(lcd_widget)
        self.hsplitter.addWidget(form)
        self.parent.resize(800, 500)
        self.hsplitter.setSizes([400, 300])    
#<<<


class EllipseMarker:
    def __init__(self, plotitem, roi_data: QRectF, angle: float=0,
                 color='r', linewidth=2, npoints=200):
        self.angle = angle / 180.0 * np.pi
        self.plotitem = plotitem
        self.npoints = npoints

        self.item = plotitem.plot(
            pen=pg.mkPen(color, width=linewidth),
            connect='all',
        )

        self.set_parameters(roi_data, self.angle)

    def set_parameters(self, roi_data: QRectF, angle: float=0):
        """Update ellipse parameters without replacing the plot item."""

        cos_theta = np.cos(angle)
        sin_theta = np.sin(angle)
        t = np.linspace(0, 2 * np.pi, self.npoints + 1)
        cos_t = np.cos(t)
        sin_t = np.sin(t)
        x0 = roi_data.center().x()
        y0 = roi_data.center().y()
        a = roi_data.width() / 2
        b = roi_data.height() / 2

        x = x0 + cos_theta * (a * cos_t - b * sin_t) \
            - sin_theta * (a * sin_t + b * cos_t)
        
        y = y0 + sin_theta * (a * cos_t - b * sin_t) \
            + cos_theta * (a * sin_t + b * cos_t)

        self.item.setData(x, y)

    def remove(self):
        self.plotitem.removeItem(self.item)


class RectangleMarker:
    def __init__(self, plotitem, roi_data: QRectF, color='r', linewidth=2):
        self.plotitem = plotitem

        self.item = plotitem.plot(
            pen=pg.mkPen(color, width=linewidth),
            connect='all',
        )

        self.set_parameters(roi_data)

    def set_parameters(self, roi: QRectF):
        """Update rect parameters without replacing the plot item."""

        x = [roi.left(), roi.right(), roi.right(), roi.left(), roi.left()]
        y = [roi.bottom(), roi.bottom(), roi.top(), roi.top(), roi.bottom()]
        self.item.setData(x, y)

    def remove(self):
        self.plotitem.removeItem(self.item)


class BeamProfilerExtension(CustomExt):

    params = [
        { 'title': 'Refresh rate [s]', 'name': 'refresh', 'type': 'float',
          'min': 0.1, 'default': 1 },
        { 'title': 'Show ROI [s]', 'name': 'show_roi', 'type': 'bool',
          'default': False },
    ]

    def __init__(self, parent: gutils.DockArea, dashboard,
                 with_dashboard_toolbar=True):
        self.camera = None
        super().__init__(parent, dashboard, add_toolbar_break=False)
        self.setup_ui()
        config_dir = get_set_config_dir("gui-state", user=True)
        settings_file_name = f'{config_dir}/{EXTENSION_NAME}.conf'
        self.qt_settings = QSettings(settings_file_name, QSettings.NativeFormat)
        self.read_settings(self.qt_settings)
        self.marker = None
        self.x = None
        self.y = None

    def setup_docks_and_widgets(self):
        self.docks['settings'] = gutils.Dock('Settings')
        self.dockarea.addDock(self.docks['settings'])
        self.docks['settings'].addWidget(self.settings_tree)

        self.docks['viewer2D'] = gutils.Dock('Camera Data')
        self.dockarea.addDock(self.docks['viewer2D'])
        self.cam_viewer = Viewer2D(QtWidgets.QWidget())
        self.docks['viewer2D'].addWidget(self.cam_viewer.parent)

        self.docks['ROIviewer'] = gutils.Dock('ROI Data')
        self.dockarea.addDock(self.docks['ROIviewer'])
        self.roi_viewer = Viewer2D(QtWidgets.QWidget())
        self.docks['ROIviewer'].addWidget(self.roi_viewer.parent)

        self.docks['lcds'] = gutils.Dock('Beam properties')
        self.dockarea.addDock(self.docks['lcds'], 'right',
                              self.docks['viewer2D'])
        self.lcd = \
            MyLCD(QtWidgets.QWidget(), Nvals=5,
                  labels=['X', 'Y', 'dx', 'dy', 'theta'])
        self.docks['lcds'].addWidget(self.lcd.parent)

        #cam_window = QtWidgets.QMainWindow()
        #dockarea = gutils.DockArea()
        #cam_window.setCentralWidget(dockarea)
        #self.camera_viewer = \
        #    DAQ_Viewer(dockarea, title='Camera', daq_type='DAQ2D')

    def setup_menus_and_toolbars(self, menubar: QtWidgets.QMenuBar = None):
        self.create_dashboard_toolbar(add_break=False)
        file_menu = self.add_menu('file', 'File', parent_menu=menubar)

    def setup_actions(self):
        self.add_action('start_profiling', 'start profiling', 'videocam',
            tip='Start continuous run')
        self.add_action('snap', 'snap', 'step', tip='Record one image')
        self.add_action('stop_profiling', 'stop profiling', 'stop',
            tip='Stop continuous run')
        self.adjust_actions(False)

    def connect_things(self):
        self.connect_action('start_profiling', self.start_profiling)
        self.connect_action('snap', self.snap)
        self.connect_action('stop_profiling', self.stop_profiling)

    def do_things_after_experiment_set(self, experiment_name: str,
                                       show_dashboard: bool = None):

        super().do_things_after_experiment_set(experiment_name, show_dashboard)
        self.camera = \
            self.modules_manager.get_mod_from_name('Beam-Camera',
                                                   ModuleType.Detector)
        self.camera.grab_done_signal.connect(self.take_data)

    def value_changed(self, param):
        """ Actions to perform when one of the param's value in self.settings
        is changed from the
        user interface

        For instance:
        if param.name() == 'do_something':
            if param.value():
                print('Do something')
                self.settings.child('main_settings',
                                    'something_done').setValue(False)

        Parameters
        ----------
        param: (Parameter) the parameter whose value just changed
        """
        pass

    def read_settings(self, qt_settings):
        geometry = qt_settings.value("geometry", QByteArray())
        self.mainwindow.restoreGeometry(geometry)
        state = qt_settings.value("dockarea", None)
        if state is not None:
            try:
                self.dockarea.restoreState(state)
            except: # pyqtgraph's state restoring is not very fail safe
                # erase inconsistent settings in case pyqtgraph trips
                qt_settings.setValue("dockarea", None)
        state = qt_settings.value("splitter")
        if state is not None:
            self.lcd.hsplitter.restoreState(state)

    def write_settings(self, qt_settings):
        qt_settings.setValue("geometry", self.mainwindow.saveGeometry())
        qt_settings.setValue("dockarea", self.dockarea.saveState())
        qt_settings.setValue("splitter", self.lcd.hsplitter.saveState())

    def _quit_fun(self) -> bool:
        self.write_settings(self.qt_settings)
        return True

    def adjust_actions(self, measuring):
        self.docks['settings'].setEnabled(not measuring)
        self._actions["start_profiling"].setEnabled(not measuring)
        self._actions["snap"].setEnabled(not measuring)
        self._actions["stop_profiling"].setEnabled(measuring)

    def snap(self):
        self.camera.snap()

    def start_profiling(self):
        self.adjust_actions(True)
        self.x = None
        self.y = None
        self.camera.grab()

    def stop_profiling(self):
        self.adjust_actions(False)
        self.camera.stop_grab()

    def get_roi(self, data, xm, ym):
        """Calculate first and second centered moment"""

        slice_x = data[xm,:]
        norm_x = sum(slice_x)
        slice_y = data[:,ym]
        norm_y = sum(slice_y)
        x0 = int(np.dot(self.x, slice_x / norm_x) + 0.5)
        y0 = int(np.dot(self.y, slice_y / norm_y)+ 0.5)
        dx = np.sqrt(np.dot((self.x - x0)**2, slice_x / norm_x))
        dy = np.sqrt(np.dot((self.y - y0)**2, slice_y / norm_y))
        return QRect(int(x0 - 4 * dx), int(y0 - 4 * dy), int(8 * dx),
                     int(8 * dy)), \
            slice_x

    def take_data(self, data: DataToExport):
        dte_raw = data.get_data_from_source('raw')  # to avoid selecting a 2D ROI
        dwa2D = dte_raw.get_data_from_dim('Data2D')[0]  #take the first 2D dwa
        raw_data = dwa2D.data[0]

        if self.x is None:
            self.x = dwa2D.axes[0].get_data()
            self.y = dwa2D.axes[1].get_data()

        # get (xm,ym) of absolute maximum 
        xm, ym = np.unravel_index(np.argmax(raw_data, axis=None), raw_data.shape)

        # first guess of moments on horizontal and vertical lines at (xm,ym)
        raw_roi, slice_x = self.get_roi(raw_data, xm, ym)

        # background subtracted but keep all positive (moments!)
        background_slice = slice_x[:int(raw_roi.left())]
        back = sum(background_slice) / raw_roi.left()
        raw_data -= back
        raw_data = np.where(raw_data < 0, 0, raw_data)

        # second guess
        back_roi, slice_x = self.get_roi(raw_data, xm, ym)

        roi_data = raw_data[back_roi.top():back_roi.bottom(),
                            back_roi.left():back_roi.right()]

        x_data = np.linspace(0, back_roi.width() - 1, back_roi.width())
        x_axis = Axis(data=x_data, label='', units='', index=0)
        y_data = np.linspace(0, back_roi.height() - 1, back_roi.height())
        y_axis = Axis(data=y_data, label='', units='', index=1)
        dfp = DataFromPlugins(name='LBS', data=[roi_data], dim='Data2D',
                              labels=['roi'], axes=[x_axis, y_axis])
        dwa_roi = DataToExport('lbs', data=[dfp])
        self.roi_viewer.show_data(dfp)

        #values = [np.array([val]) for val in [x0, y0, x1, y1, 0]]
        beam_size_values = list(lbs.beam_size(roi_data))

        lbs_roi = \
            QRectF(beam_size_values[0] - beam_size_values[2] / 2,
                   beam_size_values[1] - beam_size_values[3] / 2,
                   beam_size_values[2], beam_size_values[3])

        beam_size_values[0] += back_roi.left()
        beam_size_values[1] += back_roi.top()
        lcd_values = [np.array([val]) for val in beam_size_values]
        lcd_values[4][0] *= 180.0 / np.pi

        self.cam_viewer.show_data(dwa2D)
        self.lcd.setvalues(lcd_values)

        if self.marker is None:
            self.marker = EllipseMarker(self.roi_viewer.view.plotitem,
                                        lbs_roi, color='y')
            self.roi = RectangleMarker(self.cam_viewer.view.plotitem, raw_roi)
        else:
            self.marker.set_parameters(lbs_roi)
            self.roi.set_parameters(raw_roi)


    def take_data_moments(self, data: DataToExport):
        dte_raw = data.get_data_from_source('raw')  # to avoid selecting a 2D ROI
        dwa2D = dte_raw.get_data_from_dim('Data2D')[0]  #take the first 2D dwa

        if self.x is None:
            self.x = dwa2D.axes[0].get_data()
            self.y = dwa2D.axes[1].get_data()

        A = sum(sum(dwa2D))
        x0 = np.dot(dwa2D.data, self.x) / A
        y0 = np.dot(self.y, dwa2D.data) / A

        xc = self.x - x0
        yc = self.y - y0
        c = np.dot(xc, yc)

        a = sum(np.dot(dwa.data, xc))
        b = sum(sum(dwa2D.data * c))
        d = sum(np.dot(dwa.data, yc))

        p2 = (a + d) / 2
        sq = np.sqrt(p2 - a * d + b**2)
        lambda1 = p2 + sq
        lambda2 = p2 - sq
        if c:
            v1 = [lambda1 - d, c]
            v2 = [lambda2 - d, c]
        elif b:
            v1 = [b, lambda1 - 1]
            v2 = [b, lambda2 - 1]
        else:
            v1 = [1, 0]
            v2 = [0, 1]

        angle = np.arctan(v1[1] / v1[0]) if abs(v1[0]) > 1e-3 else np.pi/2
        self.cam_viewer.show_data(dwa2D)
        #self.lcd.setvalues(values)

        if self.marker is None:
            self.marker = EllipseMarker(
                self.cam_viewer.view.plotitem,
                x0, y0, np.sqrt(lambda1), np.sqrt(lambda2), angle,
                color='y')
        else:
            self.marker.set_parameters(x0, y0, np.sqrt(lambda1),
                                       np.sqrt(lambda2), angle)


    def take_data_lbs(self, data: DataToExport):
        dte_raw = data.get_data_from_source('raw')  # to avoid selecting a 2D ROI
        dwa2D = dte_raw.get_data_from_dim('Data2D')[0]  #take the first 2D dwa

        roi = self.cam_viewer.roi_manager.get_roi_from_index(0)
        if roi is None:
            data = dwa2D[0]
        else:
            x0, y0 = roi.roi.pos()
            width, height = roi.roi.size()
            x0, x1 = int(round(x0)), int(round(x0 + width))
            y0, y1 = int(round(y0)), int(round(y0 + height))
            data = dwa2D[0][y0:y1, x0:x1]

        values = [np.array([val]) for val in lbs.beam_size(data)]
    
        if roi is not None:
            values[0][0] += x0
            values[1][0] += y0

        values[4][0] *= 180.0 / np.pi

        self.cam_viewer.show_data(dwa2D)
        self.lcd.setvalues(values)

        if self.marker is None:
            self.marker = EllipseMarker(
                self.cam_viewer.view.plotitem,
                values[0][0], values[1][0], values[2][0], values[3][0],
                values[4][0], color='y')
        else:
            self.marker.set_parameters(values[0][0], values[1][0], values[2][0],
                                       values[3][0], values[4][0])

def main():
    """Run the extension on its own: loads a Dashboard (hidden), then the
    extension

    The Dashboard command line options apply,
    for instance ``-x EXPERIMENT_NAME -s STATE_NAME``
    """
    import sys
    from pymodaq_gui.qt_utils import mkQApp
    from pymodaq.dashboard import load_dashboard_with_arguments
    from pymodaq.dashboard import load_dashboard_with_experiment
    from pymodaq.utils.gui_utils.loader_utils import create_extension

    app = mkQApp('Custom Ext')

    win, dashboard, _ = load_dashboard_with_arguments(show_dashboard=False,
                                                      load_extension=True,
                                                      )
    win_ext, ext = \
        create_extension(dashboard, BeamProfilerExtension, show_extension=True,
                         with_dashboard_toolbar=False)

    win.mainwindow.setVisible(False)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
