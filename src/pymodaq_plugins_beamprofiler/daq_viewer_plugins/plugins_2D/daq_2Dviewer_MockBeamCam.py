import numpy as np

from qtpy.QtCore import QThread
from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter

from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, \
    comon_parameters, main
from pymodaq.utils.data import DataFromPlugins

from pymodaq_plugins_beamprofiler.hardware.controller import MockBeamCam


class DAQ_2DViewer_MockBeamCam(DAQ_Viewer_base):
    """ Instrument plugin class for a 2D viewer.
    
    TODO Complete the docstring of your plugin with:
        * The set of instruments that should be compatible with this instrument
          plugin.
        * With which instrument it has actually been tested.
        * The version of PyMoDAQ during the test.
        * The version of the operating system.
        * Installation instructions: what manufacturer’s drivers should be
          installed to make it run?

    Attributes:
    -----------
    controller: object
        The particular object that allow the communication with the hardware,
        in general a python wrapper around the hardware library.
         
    # TODO add your particular attributes here if any

    """
    device_params = [
        { 'title': 'X Pixels', 'name': 'nx', 'type': 'int', 'default': 256 },
        { 'title': 'Y Pixels', 'name': 'ny', 'type': 'int', 'default': 256 },
        { 'title': 'X0', 'name': 'x0', 'type': 'float', 'default': 128 },
        { 'title': 'Y0', 'name': 'y0', 'type': 'float', 'default': 128 },
        { 'title': 'DX', 'name': 'dx', 'type': 'float', 'default': 10 },
        { 'title': 'DY', 'name': 'dy', 'type': 'float', 'default': 12 },
        { 'title': 'Angle', 'name': 'angle', 'type': 'float', 'default': 0 },
        { 'title': 'Intensity', 'name': 'i0', 'type': 'float', 'default': 1000 },
    ]

    params = comon_parameters + device_params
    
    settings_names = [ p['name'] for p in device_params ]

    def ini_attributes(self):
        self.controller: MockBeamCam = None
        self.x_axis = None
        self.y_axis = None

    def ini_detector(self, controller=None):
        """Detector communication initialization

        Parameters
        ----------
        controller: (object)
            custom object of a PyMoDAQ plugin (Slave case). None if only one
            actuator/detector by controller (Master case)

        Returns
        -------
        info: str
        initialized: bool
            False if initialization failed otherwise True
        """
        if self.is_master:
            self.controller = \
                MockBeamCam(self.settings['nx'],
                            self.settings['ny'],
                            self.settings['x0'],
                            self.settings['y0'],
                            self.settings['dx'],
                            self.settings['dy'],
                            self.settings['angle'],
                            self.settings['i0'])
            initialized = self.controller.open_communication()
        else:
            self.controller = controller
            initialized = True

        data = self.controller.grab_image()
        data_x_axis = self.controller.x_axis()  # if possible
        self.x_axis = Axis(data=data_x_axis, label='', units='', index=1)

        data_y_axis = self.controller.y_axis()  # if possible
        self.y_axis = Axis(data=data_y_axis, label='', units='', index=0)

        dfp = DataFromPlugins(name='MockBeam', data=[data],
                              dim='Data2D', labels=['dat0'],
                              axes=[self.x_axis, self.y_axis])
        self.dte_signal_temp.emit(DataToExport('mockbeamcam', data=[dfp]))

        info = "MockBeamCam initialised"
        return info, initialized

    def close(self):
        pass

    def grab_data(self, Naverage=1, **kwargs):
        """Start a grab from the detector

        Parameters
        ----------
        Naverage: int
            Number of hardware averaging (if hardware averaging is possible,
            self.hardware_averaging should be set to True in class preamble
            and you should code this implementation)
        kwargs: dict
            others optionals arguments
        """
        QThread.msleep(10)
        data = self.controller.grab_image()
        dfp = DataFromPlugins(name='Mock1', data=data, dim='Data2D',
                              labels=['label1'],
                              axes=[self.x_axis, self.y_axis])
        self.dte_signal.emit(DataToExport('mockbeamcam', data=[dfp]))

    def stop(self):
        pass

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been
        changed by the user
        """
        if param.name() in self.settings_names:
            setattr(self.controller, param.name(), param.value())
            self.controller.update()


if __name__ == '__main__':
    main(__file__)
