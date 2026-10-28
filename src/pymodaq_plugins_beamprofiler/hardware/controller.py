from dataclasses import dataclass
import numpy as np
import colorednoise as cn
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
        self.update(self.x0, self.y0, self.dx, self.dy)
        self._init_noise()

    def _init_noise(self):
        self.noise_x = cn.powerlaw_psd_gaussian(1, 2**16)
        self.noise_y = cn.powerlaw_psd_gaussian(1, 2**16)
        self.noise_dx = cn.powerlaw_psd_gaussian(1, 2**16)
        self.noise_dy = cn.powerlaw_psd_gaussian(1, 2**16)
        self.noise_angle = cn.powerlaw_psd_gaussian(1, 2**16)
        self.current = 0

    def open_communication(self):
        return True

    def grab_image(self, Naverage=1, **kwargs):
        x0 = self.x0 + self.noise_x[self.current]
        y0 = self.y0 + self.noise_y[self.current]
        dx = max(1, self.dx + 2 * self.noise_dx[self.current])
        dy = max(1, self.dy + 2 * self.noise_dy[self.current])
        #self.angle = max(1, self.angle0 + 2 * self.noise_angle[self.current])
        self.current += 1
        if self.current == 2**16:
            self._init_noise()
        return np.random.poisson(self.data * self.i0)

    def x_axis(self):
        return self.x

    def y_axis(self):
        return self.y

    def update(self, x0=None, y0=None, dx=None, dy=None):
        if x0 is None:
            x0 = self.x0
            y0 = self.y0
            dx = self.dx
            dy = self.dy
        self.x = np.linspace(0, self.nx - 1, self.nx)
        self.y = np.linspace(0, self.ny - 1, self.ny)
        if self.angle == 0:
            self.data = \
                np.transpose(np.outer(gauss1D(self.x, x0, dx, 1),
                                      gauss1D(self.y, y0, dy, 1)))
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
