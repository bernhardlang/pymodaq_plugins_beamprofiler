import numpy as np
import pyqtgraph as pg
from qtpy import QtWidgets, QtGui
from qtpy.QtCore import QSettings, QByteArray, Qt
from pymodaq_data.data import DataToExport
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
        self.viewer0D.show_data(DataRaw(name='LCD', data=values))

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
    def __init__(self, plotitem, xc, yc, a, b, angle,
                 color='r', linewidth=2, npoints=200):
        self.plotitem = plotitem
        self.npoints = npoints

        self.item = plotitem.plot(
            pen=pg.mkPen(color, width=linewidth),
            connect='all',
        )

        self.set_parameters(xc, yc, a, b, angle)

    def set_parameters(self, xc, yc, a, b, theta):
        """Update ellipse parameters without replacing the plot item."""

        t = np.linspace(0, 2 * np.pi, self.npoints + 1)

        x = xc + a * np.cos(t) * np.cos(theta) - b * np.sin(t) * np.sin(theta)
        y = yc + a * np.cos(t) * np.sin(theta) + b * np.sin(t) * np.cos(theta)

        self.item.setData(x, y)

    def remove(self):
        self.plotitem.removeItem(self.item)


class BeamProfilerExtension(CustomExt):

    params = [
        { 'title': 'Refresh rate [s]', 'name': 'refresh', 'type': 'float',
          'min': 0.1, 'default': 1 },
    ]

    def __init__(self, parent: gutils.DockArea, dashboard,
                 with_dashboard_toolbar=True):
        super().__init__(parent, dashboard, add_toolbar_break=False)
        self.setup_ui()
        config_dir = get_set_config_dir("gui-state", user=True)
        settings_file_name = f'{config_dir}/{EXTENSION_NAME}.conf'
        self.qt_settings = QSettings(settings_file_name, QSettings.NativeFormat)
        self.read_settings(self.qt_settings)
        self.marker = None

    def setup_docks_and_widgets(self):
        self.docks['settings'] = gutils.Dock('Settings')
        self.dockarea.addDock(self.docks['settings'])
        self.docks['settings'].addWidget(self.settings_tree)

        self.docks['viewer2D'] = gutils.Dock('Camera Data')
        self.dockarea.addDock(self.docks['viewer2D'])
        self.target_viewer = Viewer2D(QtWidgets.QWidget())
        self.docks['viewer2D'].addWidget(self.target_viewer.parent)

        self.docks['lcds'] = gutils.Dock('Beam properties')
        self.dockarea.addDock(self.docks['lcds'], 'right',
                              self.docks['viewer2D'])
        self.lcd = \
            MyLCD(QtWidgets.QWidget(), Nvals=5,
                  labels=['X', 'Y', 'dx', 'dy', 'theta'])
        self.docks['lcds'].addWidget(self.lcd.parent)

        cam_window = QtWidgets.QMainWindow()
        dockarea = gutils.DockArea()
        cam_window.setCentralWidget(dockarea)
        self.camera_viewer = \
            DAQ_Viewer(dockarea, title='Camera', daq_type='DAQ2D')

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
        self.camera.grab()

    def stop_profiling(self):
        self.adjust_actions(False)
        self.camera.stop_grab()

    def take_data(self, data: DataToExport):
        dte_raw = data.get_data_from_source('raw')  # to avoid selecting a 2D ROI
        dwa2D = dte_raw.get_data_from_dim('Data2D')[0]  #take the first 2D dwa

        roi = self.target_viewer.roi_manager.get_roi_from_index(0)
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

        self.target_viewer.show_data(dwa2D)
        self.lcd.setvalues(values)

        if self.marker is None:
            self.marker = EllipseMarker(
                self.target_viewer.view.plotitem,
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
