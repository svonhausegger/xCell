from .mapper_ACT_base import MapperACTBase
from pixell import enmap, reproject
import numpy as np


class MapperACTk(MapperACTBase):
    def __init__(self, config):
        """
        config - dict
        {'file_map':path_ACT+'act_planck_dr4.01_s14s15_D56_lensing_kappa_baseline.fits',
        'file_mask':path_ACT+'act_dr4.01_s14s15_D56_lensing_mask.fits',
        'mask_name': 'mask_CMBK',
        'nside': nside,
        'mask_power': 2}
        """
        self._get_ACT_defaults(config)

    def _get_signal_map(self):
        self.pixell_mask = self._get_pixell_mask()
        mp = enmap.read_map(self.file_map)
        mp = reproject.healpix_from_enmap(mp,
                                          lmax=self.lmax,
                                          nside=self.nside)
        mp *= np.mean(self.pixell_mask**2)
        return mp

    def get_signal_map(self):
        if self.signal_map is None:
            fn = f'ACT_{self.map_name}_signal.fits.gz'
            mp = self._rerun_read_cycle(fn, 'FITSMap', self._get_signal_map)
            self.signal_map = [mp]
        return self.signal_map

    def get_dtype(self):
        return 'cmb_convergence'

    def get_spin(self):
        return 0
