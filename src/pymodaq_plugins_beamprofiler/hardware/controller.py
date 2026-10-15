from dataclasses import dataclass
import numpy as np
from pymodaq_utils.math_utils import gauss1D


@dataclass
class MockBeamCam:

    nx:  int
    ny:  int
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

    def grab_image(self, Naverage=1, **kwargs):
        return np.random.poisson(self.data * self.i0)

    def x_axis(self):
        return self.x

    def y_axis(self):
        return self.y

    def update(self):
        self.x = np.linspace(0, self.nx - 1, self.nx)
        self.y = np.linspace(0, self.ny - 1, self.ny)
        if self.angle == 0:
            self.data = \
                np.transpose(np.outer(gauss1D(self.x, self.x0, self.dx, 1),
                                      gauss1D(self.y, self.y0, self.dy, 1)))
        else:
            self.x, self.y = np.meshgrid(np.arange(self.nx), np.arange(self.ny))
            sigma_x = dx / (2 * np.sqrt(2 * np.log(2)))
            sigma_y = dy / (2 * np.sqrt(2 * np.log(2)))
            alpha = np.radians(self.angle)
            sin_a = np.sin(alpha)
            cos_a = np.cos(alpha)
            u = (self.x - x0) * cos_a + (self.y - y0) * sin_a
            v = -(self.x - x0) * sin_a + (self.y - y0) * cos_a
            self.data = np.exp(-0.5 * ((u / sigma_x)**2 + (v / sigma_y)**2))
