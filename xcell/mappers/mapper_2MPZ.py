from .mapper_base import MapperBase
from .utils import get_map_from_points, get_DIR_Nz
import fitsio
import numpy as np
import healpy as hp
import os


class Mapper2MPZ(MapperBase):
    def __init__(self, config):
        """
        config - dict
          {'data_catalog': 'Legacy_Survey_BASS-MZLS_galaxies-selection.fits',
           'mask': 'mask.fits',
           'z_edges': [0, 0.5],
           'n_jk_dir': 100,
           'mask_name': 'mask_2MPZ'}
        """
        self._get_defaults(config)
        self.z_edges = config.get('z_edges', [0, 0.5])
        self.ra_name, self.dec_name = self._get_coords(config)

        self.cat_data = None
        self.npix = hp.nside2npix(self.nside)

        # Angular mask
        self.dndz = None
        self.delta_map = None
        self.nl_coupled = None
        self.mask = None

    def _get_coords(self, config):
        coords = config.get('coordinates', 'G')
        if coords == 'G':  # Galactic
            return 'L', 'B'
        elif coords == 'C':  # Celestial/Equatorial
            return 'SUPRA', 'SUPDEC'
        else:
            raise NotImplementedError(f"Unknown coordinates {coords}")

    def get_catalog(self):
        if self.cat_data is None:
            file_data = self.config['data_catalog']
            if not os.path.isfile(file_data):
                raise ValueError(f"File {file_data} not found")
            self.cat_data = fitsio.read(file_data)
            self.cat_data = self._bin_z(self.cat_data)
            self.cat_data = self._mask_catalog(self.cat_data)

        return self.cat_data

    def _mask_catalog(self, cat):
        self.mask = self.get_mask()
        ipix = hp.ang2pix(self.nside, cat[self.ra_name],
                          cat[self.dec_name], lonlat=True)
        # Mask is binary, so 0.1 or 0.00001 doesn't really matter.
        return cat[self.mask[ipix] > 0.1]

    def _bin_z(self, cat):
        return cat[(cat['ZPHOTO'] > self.z_edges[0]) &
                   (cat['ZPHOTO'] <= self.z_edges[1])]

    def _get_specsample(self, cat):
        ids = cat['ZSPEC'] > -1
        return cat[ids]

    def _get_nz(self):
        c_p = self.get_catalog()
        c_s = self._get_specsample(c_p)
        # Sort spec sample by nested pixel index so jackknife
        # samples are spatially correlated.
        ip_s = hp.ring2nest(self.nside,
                            hp.ang2pix(self.nside,
                                       c_s[self.ra_name],
                                       c_s[self.dec_name],
                                       lonlat=True))
        idsort = np.argsort(ip_s)
        c_s = c_s[idsort]
        # Compute DIR N(z)
        z, nz, nz_jk = get_DIR_Nz(c_s, c_p,
                                  ['JCORR', 'KCORR', 'HCORR',
                                   'W1MCORR', 'W2MCORR',
                                   'BCALCORR', 'RCALCORR', 'ICALCORR'],
                                  zflag='ZSPEC',
                                  zrange=[0, 0.4],
                                  nz=100,
                                  njk=self.config.get('n_jk_dir', 100))
        zm = 0.5*(z[1:] + z[:-1])
        return {'z_mid': zm, 'nz': nz, 'nz_jk': nz_jk}

    def get_nz(self, dz=0, return_jk_error=False):
        if self.dndz is None:
            fn = 'nz_2MPZ.npz'
            self.dndz = self._rerun_read_cycle(fn, 'NPZ', self._get_nz)
        return self._get_shifted_nz(dz, return_jk_error=return_jk_error)

    def get_signal_map(self, apply_galactic_correction=True):
        if self.delta_map is None:
            d = np.zeros(self.npix)
            self.cat_data = self.get_catalog()
            self.mask = self.get_mask()
            nmap_data = get_map_from_points(self.cat_data, self.nside,
                                            ra_name=self.ra_name,
                                            dec_name=self.dec_name)
            mean_n = np.average(nmap_data, weights=self.mask)
            goodpix = self.mask > 0
            # Division by mask not really necessary, since it's binary.
            d[goodpix] = nmap_data[goodpix]/(mean_n*self.mask[goodpix])-1
            self.delta_map = d
        return [self.delta_map]

    def get_mask(self):
        if self.mask is None:
            self.mask = hp.ud_grade(hp.read_map(self.config['mask']),
                                    nside_out=self.nside)
        return self.mask

    def get_nl_coupled(self):
        if self.nl_coupled is None:
            self.cat_data = self.get_catalog()
            self.mask = self.get_mask()
            nmap_data = get_map_from_points(self.cat_data, self.nside,
                                            ra_name=self.ra_name,
                                            dec_name=self.dec_name)
            N_mean = np.average(nmap_data, weights=self.mask)
            N_mean_srad = N_mean * self.npix / (4 * np.pi)
            N_ell = np.mean(self.mask) / N_mean_srad
            self.nl_coupled = N_ell * np.ones((1, 3*self.nside))
        return self.nl_coupled

    def get_dtype(self):
        return 'galaxy_density'

    def get_spin(self):
        return 0
