from dataclasses import dataclass
import numpy as np
from pymodaq_utils.math_utils import gauss1D


@dataclass
class MockBeamCam:

    xpix:  int
    ypix:  int
    x0:    int
    y0:    int
    dx:    float
    dy:    float
    angle: float
    i0:    float
    
    def __post_init__(self):
        self.update()

    def open_communication(self):
        return True

    def grab_data(self, Naverage=1, **kwargs):
        return np.random.poisson(self.data * self.i0)

    def update(self):
        self.x_axis = np.linspace(0, self.xpix - 1, self.xpix)
        self.y_axis = np.linspace(0, self.ypix - 1, self.ypix)
        if self.angle == 0:
            self.data = np.transpose(np.outer(gauss1D(self.x_axis, self.x0,
                                                      self.dx, 1),
                                              gauss1D(self.y_axis, self.y0,
                                                      self.dy, 1)))
        else:
            x, y = np.meshgrid(np.arange(nx), np.arange(ny))
            sigma_x = dx / (2 * np.sqrt(2 * np.log(2)))
            sigma_y = dy / (2 * np.sqrt(2 * np.log(2)))
            alpha = np.radians(angle)
            sin_a = np.sin(alpha)
            cos_a = np.cos(alpha)
            u = (x - x0) * cos_a + (y - y0) * sin_a
            v = -(x - x0) * sin_a + (y - y0) * cos_a
            self.data = np.exp(-0.5 * ((u / sigma_x)**2 + (v / sigma_y)**2))
