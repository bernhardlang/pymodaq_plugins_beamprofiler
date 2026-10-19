from qtpy import QtWidgets

from pymodaq_gui import utils as gutils
from pymodaq_gui.plotting.data_viewers.viewer2D import Viewer2D
from pymodaq_gui.utils.widgets.lcd import LCD
from pymodaq.control_modules.daq_viewer import DAQ_Viewer
from pymodaq_utils.config import GlobalConfig
from pymodaq_utils.logger import set_logger, get_module_name
from pymodaq.utils.custom_ext import CustomExt

logger = set_logger(get_module_name(__file__))

config = GlobalConfig()

EXTENSION_NAME = 'BeamProfiler'
CLASS_NAME = 'BeamProfilerExtension'


class BeamProfilerExtension(CustomExt):

    params = [
        { 'title': 'Refresh rate [s]', 'name': 'refresh', 'type': 'float',
          'min': 0.1, 'default': 1 },
    ]

    def __init__(self, parent: gutils.DockArea, dashboard):
        super().__init__(parent, dashboard, add_toolbar_break=False)
        self.setup_ui()

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
            LCD(QtWidgets.QWidget(), Nvals=5,
                labels=['X', 'Y', 'dx', 'dy', 'theta'])
        self.docks['lcds'].addWidget(self.lcd.parent)

        cam_window = QtWidgets.QMainWindow()
        dockarea = gutils.DockArea()
        cam_window.setCentralWidget(dockarea)
        self.camera_viewer = \
            DAQ_Viewer(dockarea, title='BSCamera', daq_type='DAQ2D')

    def setup_menus_and_toolbars(self, menubar: QtWidgets.QMenuBar = None):
        """Non mandatory method to be subclassed in order to create menus
        and toolbars

        Examples
        --------
        >>>file_menu = self.add_menu('file', 'File', parent_menu=menubar)

        See Also
        --------
        pymodaq.utils.managers.action_manager.ActionManager
        """
        # adds a second toolbar, the Dashboard one: show/hide the Dashboard,
        # load an experiment and a state
        self.create_dashboard_toolbar(add_break=False)
        file_menu = self.add_menu('file', 'File', parent_menu=menubar)

    def setup_actions(self):
        self.add_action('start_profiling', 'start profiling', 'add_circle',
            tip='Start continuous run')
        self.add_action('stop_profiling', 'stop profiling', 'minus_circle',
            tip='Stop continuous run')
        self.add_action('snap', 'snap', 'add_circle', tip='Record one image')

    def connect_things(self):
        self.connect_action('start_profiling', self.start_profiling)
        self.connect_action('snap', self.snap)

    def do_things_after_experiment_set(self, experiment_name: str,
                                       show_dashboard: bool = None):
        super().do_things_after_experiment_set(experiment_name, show_dashboard)
        self.camera = \
            self.modules_manager.get_mod_from_name('Beam-Camera',
                                                   ModuleType.Detector)
        self.camera.grab_done.connect(self.take_data)

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

    def _quit_fun(self) -> bool:
        """Called when the extension is closed. Return True to let it quit,
        False to refuse (for instance while running). The base class returns
        None, which would prevent the extension from closing.
        """
        return True

    def snap(self):
        pass

    def start_profiling(self):
        pass

    def stop_profiling(self):
        pass

    def take_data(self, data: DataToExport):
        pass


def main():
    """Run the extension on its own: loads a Dashboard (hidden), then the
    extension

    The Dashboard command line options apply,
    for instance ``-x EXPERIMENT_NAME -s STATE_NAME``
    """
    import sys
    from pymodaq_gui.qt_utils import mkQApp
    from pymodaq.dashboard import load_dashboard_with_arguments
    from pymodaq.utils.gui_utils.loader_utils import create_extension

    app = mkQApp('Custom Ext')

    win, dashboard, _ = load_dashboard_with_arguments(show_dashboard=False,
                                                      load_extension=False,
                                                      )
    win.mainwindow.setVisible(False)

    win_ext, ext = \
        create_extension(dashboard, BeamProfilerExtension, show_extension=True)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
