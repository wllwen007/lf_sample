import scipy as sp
import pylab as pl
import numpy as np
import os
import multiprocessing as mp
import itertools

import scipy.optimize as so
from scipy.interpolate import interp1d
from astropy.table import Table
from astropy.io import fits
import astropy.units as u
#from astropy.cosmology import FlatLambdaCDM
#acosmo = FlatLambdaCDM(H0=70, Om0=0.3)
from astropy.cosmology import LambdaCDM
acosmo = LambdaCDM(H0=70, Om0=0.3, Ode0=0.7)

MODPATH = os.path.dirname(__file__)

class completenessf(object):
    def __init__(self,npyfile):
        area_i,irangep,fraction_total_MC_mean,fraction_total_MC_sig,fraction_total_MC_mean_perArea = np.load(npyfile)
        irangep = irangep/1000.
        
        self.C_flux_interp = interp1d(irangep,fraction_total_MC_mean,kind='cubic', bounds_error=False, fill_value=(np.min(fraction_total_MC_mean),1))
        return
    
    def get_val(self, flux):
        #print flux, np.min(self.C_flux_interp.x), np.max(self.C_flux_interp.x)
        return self.C_flux_interp(flux)

def mp_vax(arg, **kwarg):
    return rmsmap.vmax(*arg, **kwarg)
    

class rmsmapz_old(object):
    def __init__(self,map,sampling=100):
        # map is a 2D nan-blanked FITS array as produced by PyBDSF
        hdu=fits.open(map)
        self.data=hdu[0].data
        self.sampling=sampling
        self.min=np.nanmin(self.data)
        self.max=np.nanmax(self.data)
        #print self.min,self.max
        self.bins=np.logspace(np.log10(self.min),np.log10(self.max),sampling+1)
        self.centres=0.5*(self.bins[:-1]+self.bins[1:])
        cdata=self.data[~np.isnan(self.data)]
        self.hist=np.asfarray(np.histogram(cdata,self.bins)[0])/len(cdata)
        self.area=len(cdata)*hdu[0].header['CDELT1']**2.0 # in sq. deg
        
        degtost = (180./np.pi)**2.  # sq degrees to steradians 
        self.area_sr= self.area/degtost
        self.domega=self.area_sr / (4.*np.pi)
        print('Read',map,'area is {:.3f} deg^2'.format(self.area))
        print('Read',map,'area is {:.3f} percent of sky'.format(self.domega))

    def vmax(self,zmax,L):
        # compute the Smolcic Ak*V_max(L,rms_k) sum
        vm = self.domega*self.get_vmax(L,self.centres)
        return np.sum(self.hist*vm)

    def vmin(self,zmin,L):
        # compute the Smolcic Ak*V_max(L,rms_k) sum
        #DL = acosmo.luminosity_distance(zmin).value
        #vc = (4.*np.pi/3.)*(DL/(1.+zmin))**3.  # volume at zlim
        #vmax = domega*vc
        #vm = cosmo.distance.comoving_volume(zmin, **default_cosmo)
        vm = self.domega*acosmo.comoving_volume(zmin).value
        return np.sum(self.hist*vm)
    
    def interp_setup(self,Lmin,Lmax,factor,alpha=-0.7):
        # we solve in terms of r = L/(factor*rms)
        self.factor=factor
        self.alpha=alpha
        rmin=Lmin/(factor*self.max)
        rmax=Lmax/(factor*self.min)
        print('Using r range {:.2e} to {:.2e}'.format(rmin,rmax))
        rvals=np.linspace(np.log10(rmin),np.log10(rmax),self.sampling)
        zvals=np.zeros_like(rvals)
        for i in range(len(rvals)):
            #print i,rvals[i]
            try:
                zvals[i]=so.brentq(lambda z: RadioFlux(10**rvals[i],z,alpha)-1,0,100)
            except ValueError:
                zvals[i]=100.
        self.get_zmax_interp=interp1d(rvals,zvals,kind='cubic', bounds_error=False, fill_value=(0,20))
        #self.get_zmax_interp=interp1d(rvals,zvals,kind='cubic')

    def get_vmax(self,L,rms):
        # uses interpolation so can work with array-like rms
        #print np.log10(L/(rms*self.factor)), np.min(self.get_zmax_interp.x), np.max(self.get_zmax_interp.x)
        zlim=self.get_zmax_interp(np.log10(L/(rms*self.factor)))

        #DL = acosmo.luminosity_distance(zlim).value
        #vc = (4.*np.pi/3.)*(DL/(1.+zlim))**3.  # volume at zlim
        #vmax = domega*vc
        vmax = acosmo.comoving_volume(zlim).value
        #vmax = cosmo.distance.comoving_volume(zlim, **default_cosmo)
        return vmax
    
class rmsmapz(object):
    def __init__(self,map,sampling=100):
        # map is a 2D nan-blanked FITS array as produced by PyBDSF
        hdu=fits.open(map)
        self.data=hdu[0].data
        self.sampling=sampling
        self.min=np.nanmin(self.data)
        self.max=np.nanmax(self.data)
        #print self.min,self.max
        self.bins=np.logspace(np.log10(self.min),np.log10(self.max),sampling+1)
        self.centres=0.5*(self.bins[:-1]+self.bins[1:])
        cdata=self.data[~np.isnan(self.data)]
        self.hist=np.asfarray(np.histogram(cdata,self.bins)[0])/len(cdata)
        self.area=len(cdata)*hdu[0].header['CDELT1']**2.0 # in sq. deg
        
        degtost = (180./np.pi)**2.  # sq degrees to steradians 
        self.area_sr= self.area/degtost
        self.domega=self.area_sr / (4.*np.pi)
        print('Read',map,'area is {:.3f} deg^2'.format(self.area))
        print('Read',map,'area is {:.3f} percent of sky'.format(self.domega))

    #def vmax(self,L):
        ## compute the Smolcic Ak*V_max(L,rms_k) sum
        #vm = self.domega*self.get_vmax(L,self.centres)
        #return np.sum(self.hist*vm)


    def vmax(self,zmax,L):
        # compute the Smolcic Ak*V_max(L,rms_k) sum
        vm_max = self.domega*acosmo.comoving_volume(zmax).value
        vm = self.domega*self.get_vmax(L,self.centres) # max vol per rms slice
        vm[vm>=vm_max] = vm_max   # maxes out at vm_max  ### TESTING
        return np.sum(self.hist*vm)
    
    #def vmax(self,z,L):
        ## compute the Smolcic Ak*V_max(L,rms_k) sum
        ##DL = acosmo.luminosity_distance(zmin).value
        ##vc = (4.*np.pi/3.)*(DL/(1.+zmin))**3.  # volume at zlim
        ##vmax = domega*vc
        ##vm = cosmo.distance.comoving_volume(zmin, **default_cosmo)
        ##import ipdb; ipdb.set_trace()
        #Flux = RadioFlux(L,z,alpha=-0.7)
        #Af = np.sum(self.hist[ self.centres  < Flux/self.factor])  ## fraction of map where this source is detectable at the lower z limit
        #vm = Af*self.domega*acosmo.comoving_volume(z).value
        #return np.sum(self.hist*vm)

    def vmin(self,zmin,L):
        # compute the Smolcic Ak*V_max(L,rms_k) sum
        vm_min = self.domega*acosmo.comoving_volume(zmin).value
        vm = self.domega*self.get_vmax(L,self.centres)  # max vol per rms slice
        vm[vm>=vm_min] = vm_min    # vmin can't exceed vmax for a given rms value
        
        ##vm = vm_min    ### TESTING
        return np.sum(self.hist*vm)
    
    #def vmin(self,zmin,z,L):
        ## compute the Smolcic Ak*V_max(L,rms_k) sum
        ##DL = acosmo.luminosity_distance(zmin).value
        ##vc = (4.*np.pi/3.)*(DL/(1.+zmin))**3.  # volume at zlim
        ##vmax = domega*vc
        ##vm = cosmo.distance.comoving_volume(zmin, **default_cosmo)
        ##import ipdb; ipdb.set_trace()
        #Flux = RadioFlux(L,z,alpha=-0.7)
        #Af = np.sum(self.hist[ self.centres  < Flux/self.factor])  ## fraction of map where this source is detectable at the lower z limit
        #vm = Af*self.domega*acosmo.comoving_volume(zmin).value
        #return np.sum(self.hist*vm)
    
    def interp_setup(self,Lmin,Lmax,factor,alpha=-0.7):
        # we solve in terms of r = L/(factor*rms)
        self.factor=factor
        self.alpha=alpha
        rmin=Lmin/(factor*self.max)
        rmax=Lmax/(factor*self.min)
        print('Using r range {:.2e} to {:.2e}'.format(rmin,rmax))
        rvals=np.linspace(np.log10(rmin),np.log10(rmax),self.sampling)
        zvals=np.zeros_like(rvals)
        for i in range(len(rvals)):
            #print i,rvals[i]
            try:
                zvals[i]=so.brentq(lambda z: RadioFlux(10**rvals[i],z,alpha)-1,0,100)
            except ValueError:
                zvals[i]=100.
        self.get_zmax_interp=interp1d(rvals,zvals,kind='cubic', bounds_error=False, fill_value=(0,20))
        #self.get_zmax_interp=interp1d(rvals,zvals,kind='cubic')

    def get_vmax(self,L,rms):
        # uses interpolation so can work with array-like rms
        #print np.log10(L/(rms*self.factor)), np.min(self.get_zmax_interp.x), np.max(self.get_zmax_interp.x)
        zlim=self.get_zmax_interp(np.log10(L/(rms*self.factor)))

        #DL = acosmo.luminosity_distance(zlim).value
        #vc = (4.*np.pi/3.)*(DL/(1.+zlim))**3.  # volume at zlim
        #vmax = domega*vc
        vmax = acosmo.comoving_volume(zlim).value
        #vmax = cosmo.distance.comoving_volume(zlim, **default_cosmo)
        return vmax
    
    
class rmsz(rmsmapz):
    ''' a class to use stored data instead of computing the histogram directly'''
    
    def __init__(self,npyfile):
        
        rms = np.load(npyfile)
        
        self.sampling = rms['sampling']
        
        self.bins = rms['bins']
        
        self.centres = rms['centres']
        self.hist = rms['hist']
        self.area = float(rms['area'])
        self.max = rms['dmax']
        self.min = rms['dmin']
        
        degtost = (180./np.pi)**2.  # sq degrees to steradians 
        self.area_sr= self.area/degtost
        self.domega=self.area_sr / (4.*np.pi)
        print('Read',npyfile,'area is {:.2f} deg^2'.format(self.area))
        print('Read',npyfile,'area is {:.2f} percent of sky'.format(100*self.domega))
        
        return


def RadioPower(Flux, z, alpha=-0.7):
    """RadioPower(Flux, z, alpha=-0.7)
args
    Flux - in Jy
    z - redshift 
kwargs
    alpha  - spectral index (default = -0.7) defined in the sensee S \propto nu^alpha
    """
    # flux in Jy to Power in W/Hz
    #DL = cosmo.distance.luminosity_distance(z, **default_cosmo)
    DL = acosmo.luminosity_distance(z).value   # in Mpc
    A = (4.*np.pi*(DL**2.)*(3.08667758e22**2.))      # in SI (m^2)
    S = Flux*1.e-26                            # kg /s^2
    power = (S*A) / ((1. + z)**(1.+alpha))
    return power


def RadioFlux (power, z, alpha=-0.7): 
    # function to calculate flux density given in Jy some radio power
    #DL = cosmo.distance.luminosity_distance(z, **default_cosmo)
    DL = acosmo.luminosity_distance(z).value
    A = (4.*np.pi*(DL**2.)*(3.08667758e22**2.))      # in SI (m^2)
    Flux = (power  / A) *((1. + z)**(1.+alpha) )
    S = 1e26* Flux   # in Jy
    return S

def OpticalLuminosity(Flux, z):
    # flux in W/Hz/m^2 to luminosity in W/Hz
    #DL = cosmo.distance.luminosity_distance(z, **default_cosmo)
    S = Flux*1.e-26                            # kg /s^2
    DL = acosmo.luminosity_distance(z).value
    A = (4.*np.pi*(DL**2.)*(3.08667758e22**2.))      # in SI (m^2)
    luminosity = S*A*(1. + z)
    return luminosity

def OpticalFlux (luminosity, z): 
    # function to calculate flux density given some optical luminosity
    #DL = cosmo.distance.luminosity_distance(z, **default_cosmo)
    DL = acosmo.luminosity_distance(z).value
    A = (4.*np.pi*(DL**2.)*(3.08667758e22**2.))      # in SI (m^2)
    S = luminosity / ( A*(1. + z) )
    Flux = S*1e26                  # to Jy
    return Flux


def OpticalLuminosity2(Flux, z, alpha):
    # flux in W/Hz/m^2 to luminosity in W/Hz
    #DL = cosmo.distance.luminosity_distance(z, **default_cosmo)
    DL = acosmo.luminosity_distance(z).value
    A = (4.*np.pi*(DL**2.)*(3.08667758e22**2.))      # in SI (m^2)
    luminosity = Flux*A*(1. + z)**(1.+alpha)
    return luminosity


def OpticalMag(mag, z):
    #dm = cosmo.magnitudes.distance_modulus(z, **default_cosmo)
    dm = acosmo.distmod(z).value
    Mag = mag - dm
    return Mag

def XrayLuminosity(Flux, z):
    # flux in W/m^2 to luminosity in W
    #DL = cosmo.distance.luminosity_distance(z, **default_cosmo)
    DL = acosmo.luminosity_distance(z).value
    luminosity = Flux*4.*np.pi*(DL**2.)*(3.08667758e22**2.)  #*(1. + z) these are X-ray bolometric
    luminosity = luminosity*1e7  # W -> erg/s
    return luminosity


def match_indices(x1,x2):
    xind1 = []
    xind2 = []
    for i1,x1i in enumerate(x1):
        i2 = np.where(x2==x1i)[0]
        if len(i2) > 0:
            xind1.append(i1)
            xind2.append(i2[0])
    return xind1,xind2
    
def zlim_func(x,m,z,mlim):
    '''
    function whose zero is the maximum z at which target with magnitude m can be observed given the magnitude limit mlim
    f(x) = mlim - DM(x) - m + DM(z)
    '''
    #f = mlim -m + cosmo.magnitudes.distance_modulus(z, **default_cosmo) - cosmo.magnitudes.distance_modulus(x, **default_cosmo)
    f = mlim -m +  acosmo.distmod(z).value -  acosmo.distmod(x).value
    #print mlim, m, cosmo.magnitudes.distance_modulus(z, **default_cosmo), cosmo.magnitudes.distance_modulus(x, **default_cosmo), x
    return f
    
def vmax(m,z,mlim,area):
    '''
    input - m : observed magnitude of source
            z : redshift of source
         mlim : magnitude limit of survey
         area : in sq degrees
   output - vmax : maximum volume in which source could be observed
    '''
    # find zero - where M = Mlim
    f0 = zlim_func(0.,m,z,mlim)
    f10 = zlim_func(10.,m,z,mlim)
    if f0*f10 < 0:
        try:
            zlim = sp.optimize.brentq(zlim_func, 0., 10., args=(m,z,mlim))
        except RuntimeError:
            print('solve not converging %.3f, %.3f, %.3f' %(m,z,mlim))
            zlim = np.nan
            return np.nan
    else:
        zlim = np.nan
        return np.nan
    
    ## for checking
    #M = m - cosmo.magnitudes.distance_modulus(z, **default_cosmo)
    #Mlim = mlim - cosmo.magnitudes.distance_modulus(zlim, **default_cosmo)
    #print 'M(z=%.3f) = %.2f' %(z,M)
    #print 'Mlim(zlim=%.3f) = %.2f' %(zlim,Mlim)
    
    degtost = 4.*180.**2./np.pi  # sq degrees to steradians
    domega = area/degtost
    #DL = cosmo.distance.luminosity_distance(zlim, **default_cosmo)
    DL = acosmo.luminosity_distance(zlim).value
    vc = (4.*np.pi/3.)*(DL/(1+zlim))**3.  # volume at zlim
    vmax = domega*vc
    return vmax


def func_star(i_args):
    """Convert `f([1,2])` to `f(1,2)` call."""
    return calc_stuff(*i_args)

    
def func_star_min(i_args):
    """Convert `f([1,2])` to `f(1,2)` call."""
    return calc_stuff_min(*i_args)


def calc_stuff(i,args):
    z,L,fluxlim2,stype = args
    zt = np.arange(5,-0.001,-0.01) + z[i]
    if stype == 'Radio':
        ft = RadioFlux(L[i], zt, alpha=-0.7)
    elif stype == 'Optical':
        ft = OpticalFlux(L[i], zt)
    zm = np.interp(fluxlim2, ft, zt)
    #Vzmax = cosmo.distance.comoving_volume(zm, **default_cosmo)
    Vzmax = acosmo.comoving_volume(zm).value
    return Vzmax


def calc_stuff_min(i,args):
    z,L,fluxlim2,stype = args
    zt = np.arange(z[i],-0.001,-0.001)
    if stype == 'Radio':
        ft = RadioFlux(L[i], zt, alpha=-0.7)
    elif stype == 'Optical':
        ft = OpticalFlux(L[i], zt)
    zm = np.interp(fluxlim2, ft, zt)
    #Vzmin[i] = zm
    #Vzmin = cosmo.distance.comoving_volume(zm, **default_cosmo)
    Vzmin = acosmo.comoving_volume(zm).value
    return Vzmin
    
    
def get_Vzmax(z, L, fluxlim2, domega, zmax=10., stype='Radio',filename='Vzmax.sav.npy', clobber=False, rmsmap=None, completeness=None, verbose=False, savefile=True):
    
    
    if os.path.isfile(filename) and (not clobber):
        print('read Vzmax from '+filename)
        Vzmax = np.load(filename)
    else:
        if os.path.isfile(filename): os.system('rm -rf '+filename)
        Vzmax = np.zeros(0)
        
    Nsrc2 = len(z)
    if len(Vzmax) != len(z):
        print('calculating Vzmax for '+filename)
        Vzmax   = np.zeros(Nsrc2)
        
        if (rmsmap is None) or (stype=='Optical'):
            #for i in range( 0, Nsrc2):
                #zt = np.arange(5,-0.001,-0.01) + z[i]
                #if stype == 'Radio':
                    #ft = RadioFlux(L[i], zt, alpha=-0.7)
                #elif stype == 'Optical':
                    #ft = OpticalFlux(L[i], zt)
                #zm = np.interp(fluxlim2, ft, zt)
                #Vzmax[i] = cosmo.distance.comoving_volume(zm, **default_cosmo)

    
    
            pool = mp.Pool(np.min((16,mp.cpu_count())))
            Vzmax = np.array(pool.map(func_star, zip(list(range(Nsrc2)), itertools.repeat([z,L,fluxlim2,stype]))))
            Vzmax = domega*Vzmax
            
        # handle the varying rms case
        else:
            if not isinstance(rmsmap, rmsmapz):
                print("ERROR, rmsmap instance not initialised/passed properly")
                sys.exit(1)
            for i in range( 0, Nsrc2):
                #import ipdb; ipdb.set_trace()
                Vzmax[i] = rmsmap.vmax(zmax,L[i])
                #print 'test pool1'
                #pool = mp.Pool(np.min((16,mp.cpu_count())))
                #Vzmax = np.array(pool.map(mp_vax, itertools.izip(itertools.repeat(rmsmap), L)   ))
                
        if (completeness is not None) and (stype=='Radio'):
            if not isinstance(completeness, completenessf):
                print("ERROR, completeness instance not initialised/passed properly")
                sys.exit(1)
            for i in range( 0, Nsrc2):
                ft = RadioFlux(L[i], z[i], alpha=-0.7)
                #print completeness.get_val(ft)
                if verbose:
                    print(ft, completeness.get_val(ft),  Vzmax[i], Vzmax[i]*completeness.get_val(ft))
                Vzmax[i] = Vzmax[i]*completeness.get_val(ft)
                #Vzmax[i] = Vzmax[i]/completeness.get_val(ft)
                
        if savefile:    
            np.save(filename, (Vzmax))
        
        
    return Vzmax


def get_zmax1(zi, Li, fluxlim2, stype):
    zt = np.arange(5,-0.001,-0.01) + zi
    if stype == 'Radio':
        ft = RadioFlux(Li, zt, alpha=-0.7)
    elif stype == 'Optical':
        ft = OpticalFlux(Li, zt)
    zm = np.interp(fluxlim2, ft, zt)
    return zm

def func_star_zmax1():
    return


def get_zmax_mp(z, L, fluxlim2, stype='Radio',filename='zmax.sav.npy', clobber=False):
    if os.path.isfile(filename) and (not clobber):
        print('read zmax from '+filename)
        zmax = np.load(filename)
    else:
        if os.path.isfile(filename): os.system('rm -rf '+filename)
        zmax = np.zeros(0)
    Nsrc2 = len(z)
    if len(zmax) != len(z):
        print('calculating zmax for '+filename)
        pool = mp.Pool(np.min((16,mp.cpu_count())))
        #results = [pool.apply_async(get_zmax1, args=(zi,Li,fluxlim2,stype)) for zi, Li in zip(z,L)]
        #zmax =  [p.get() for p in results]
        #zmax = np.array(zmax)
        zmax = np.array(pool.map(func_star_zmax1, zip(list(range(Nsrc2)), itertools.repeat([z,L,fluxlim2,stype]))))
        np.save(filename, (zmax))
    return zmax


def get_zmax(z, L, fluxlim2, stype='Radio',filename='zmax.sav.npy', clobber=False):
    if os.path.isfile(filename) and (not clobber):
        print('read zmax from '+filename)
        zmax = np.load(filename)
    else:
        if os.path.isfile(filename): os.system('rm -rf '+filename)
        zmax = np.zeros(0)
    Nsrc2 = len(z)
    if len(zmax) != len(z):
        print('calculating zmax for '+filename)
        zmax   = np.zeros(Nsrc2)
        for i in range( 0, Nsrc2):
            zt = np.arange(5,-0.001,-0.01) + z[i]
            if stype == 'Radio':
                ft = RadioFlux(L[i], zt, alpha=-0.7)
            elif stype == 'Optical':
                ft = OpticalFlux(L[i], zt)
            zm = np.interp(fluxlim2, ft, zt)
            zmax[i] = zm
        np.save(filename, (zmax))
    return zmax


def get_Vzmin_old(z, L, fluxlim2, stype='Radio',filename='Vzmin.sav.npy', clobber=False):
    '''
    NB not implementing rmsmap yet for zmin... this mostly applies to optical
    '''
    if os.path.isfile(filename) and (not clobber):
        print('read Vzmin from '+filename)
        Vzmin = np.load(filename)
    else:
        if os.path.isfile(filename): os.system('rm -rf '+filename)
        Vzmin = np.zeros(0)
    Nsrc2 = len(z)
    if len(Vzmin) != len(z):
        print('calculating Vzmin for '+filename)
        Vzmin   = np.zeros(Nsrc2)
        
        for i in range( 0, Nsrc2):
            zt = np.arange(z[i],-0.001,-0.001)
            if stype == 'Radio':
                ft = RadioFlux(L[i], zt, alpha=-0.7)
            elif stype == 'Optical':
                ft = OpticalFlux(L[i], zt)
            zm = np.interp(fluxlim2, ft, zt)
            #Vzmin[i] = zm
            Vzmin[i] = acosmo.comoving_volume(zm).value
            
        np.save(filename, (Vzmin))
    return Vzmin



def get_Vzmin(z, L, fluxlim2, domega, zmin=0, stype='Radio',filename='Vzmin.sav.npy', clobber=False, rmsmap=None, completeness=None, verbose=False, savefile=True):
    
    if os.path.isfile(filename) and (not clobber):
        print('read Vzmin from '+filename)
        Vzmin = np.load(filename)
    else:
        if os.path.isfile(filename): os.system('rm -rf '+filename)
        Vzmin = np.zeros(0)
        
    Nsrc2 = len(z)
    if len(Vzmin) != len(z):
        print('calculating Vzmin for '+filename)
        Vzmin   = np.zeros(Nsrc2)
        
        if (rmsmap is None):
            #for i in range( 0, Nsrc2):
                #zt = np.arange(z[i],-0.001,-0.001)
                #if stype == 'Radio':
                    #ft = RadioFlux(L[i], zt, alpha=-0.7)
                #elif stype == 'Optical':
                    #ft = OpticalFlux(L[i], zt)
                #zm = np.interp(fluxlim2, ft, zt)
                ##Vzmin[i] = zm
                #Vzmin[i] = cosmo.distance.comoving_volume(zm, **default_cosmo)
                
            if np.isfinite(fluxlim2):
                
                pool = mp.Pool(np.min((16,mp.cpu_count())))
                Vzmin = np.array(pool.map(func_star_min, zip(list(range(Nsrc2)), itertools.repeat([z,L,fluxlim2,stype]))))
                Vzmin = domega*Vzmin
            else:
                Vzmin = np.zeros(Nsrc2)
                
                
            Vzmin_lim = domega*acosmo.comoving_volume(zmin).value * np.ones(Nsrc2)
            
            Vzmin = np.maximum(Vzmin, Vzmin_lim)
            
                
        # handle the varying rms case
        else:
            if not isinstance(rmsmap, rmsmapz):
                print("ERROR, rmsmap instance not initialised/passed properly, using zlim")
                sys.exit(1)
            else:
                for i in range( 0, Nsrc2):
                    Vzmin[i] = rmsmap.vmin(zmin,L[i])
                
        if (completeness is not None) and (stype=='Radio'):
            if not isinstance(completeness, completenessf):
                print("ERROR, completeness instance not initialised/passed properly")
                sys.exit(1)
            for i in range( 0, Nsrc2):
                ft = RadioFlux(L[i], z[i], alpha=-0.7)
                #print completeness.get_val(ft)
                if verbose:
                    print(ft, completeness.get_val(ft),  Vzmin[i], Vzmin[i]*completeness.get_val(ft))
                Vzmin[i] = Vzmin[i]*completeness.get_val(ft)
        if savefile:    
            np.save(filename, (Vzmin))
        
        
    return Vzmin


def get_zmin1(zi, Li, fluxlim2, stype):
    zt = np.arange(zi,-0.001,-0.001)
    if stype == 'Radio':
        ft = RadioFlux(Li, zt, alpha=-0.7)
    elif stype == 'Optical':
        ft = OpticalFlux(Li, zt)
    zm = np.interp(fluxlim2, ft, zt)
    return zm



def get_zmin_mp(z, L, fluxlim2, stype='Radio',filename='zmin.sav.npy', clobber=False):
    if os.path.isfile(filename) and (not clobber):
        print('read zmin from '+filename)
        zmin = np.load(filename)
    else:
        if os.path.isfile(filename): os.system('rm -rf '+filename)
        zmin = np.zeros(0)
    Nsrc2 = len(z)
    if len(zmin) != len(z):
        print('calculating zmin for '+filename)
        pool = mp.Pool(np.min((16,mp.cpu_count())))
        results = [pool.apply_async(get_zmin1, args=(zi,Li,fluxlim2,stype)) for zi, Li in zip(z,L)]
        zmin =  [p.get() for p in results]
        zmin = np.array(zmin)
        np.save(filename, (zmin))
    return zmin


def get_zmin(z, L, fluxlim2, stype='Radio',filename='zmin.sav.npy', clobber=False):
    if os.path.isfile(filename) and (not clobber):
        print('read zmin from '+filename)
        zmin = np.load(filename)
    else:
        if os.path.isfile(filename): os.system('rm -rf '+filename)
        zmin = np.zeros(0)
    Nsrc2 = len(z)
    if len(zmin) != len(z):
        print('calculating zmin for '+filename)
        zmin   = np.zeros(Nsrc2)
        for i in range( 0, Nsrc2):
            zt = np.arange(z[i],-0.001,-0.001)
            if stype == 'Radio':
                ft = RadioFlux(L[i], zt, alpha=-0.7)
            elif stype == 'Optical':
                ft = OpticalFlux(L[i], zt)
            zm = np.interp(fluxlim2, ft, zt)
            zmin[i] = zm
        np.save(filename, (zmin))
    return zmin

def get_LF(pbins, power, zmin, zmax, area, ind=None, verbose=True):
    '''
    pbins - bins of power (giving bin boundaries)
    power - log10(power) values
    zmin - for each source minimum z it could be observed (taking into account all selections)
    zmax - for each source maximum z it could be observed
    area - of survey in steradians
    ind - optically specify a selection index
    
    The differential comoving volume element dV_c/dz/dSolidAngle.
    Dimensions are volume per unit redshift per unit solid angle.
    Units are Mpc**3 Steradians^-1.
    '''
    print("Calculating LF: {n} sources".format(n=len(power)))
    if ind is not None:
        power = power[ind]
        zmin = zmin[ind]
        zmax = zmax[ind]
        print("sub-selected {n} sources".format(n=len(power)))
    
    # number of bins
    N_P_bins = len(pbins) - 1
    
    # bin widths
    dp = pbins[1:] - pbins[:-1]
    
    rho  = np.nan*np.ones((N_P_bins))
    rhoerr  = np.nan*np.ones((N_P_bins))
    num   = np.nan*np.ones((N_P_bins))
    for P_i in range( N_P_bins ): #loop over log P
        # count  #
        sel_ind = np.where( (power > pbins[P_i])  & (power <= pbins[P_i + 1]) )[0]
        #powerhigh = pbins[P_i + 1]
        
        if len(sel_ind) > 1:  # need at least 2 in a bin
            zmax_h = zmax[sel_ind]
            zmin_h = zmin[sel_ind]
            
            vzmax = acosmo.comoving_volume(zmax_h).value
            vzmin = acosmo.comoving_volume(zmin_h).value
            
            vi = (vzmax - vzmin)*(area/(4.*np.pi))
            rho[P_i]  =  np.sum(1./vi)      #sum of 1/v_max for each source
            #rhoerr[P_i] =  rho[P_i]*np.sqrt(float(len(sel_ind)))/float(len(sel_ind))
            rhoerr[P_i] = np.sqrt(np.sum((1./vi)**2.))
            num[P_i]  =  float(len(sel_ind))
            if np.isnan(rho[P_i]):
                print(num)
                print(vi)
        if verbose:
            print("{p1:7.2f} < P <= {p2:6.2f} ({n:.0f}) : {rho:6.2e} +/- {rhoerr:6.2e}".format(p1=pbins[P_i], p2=pbins[P_i + 1], rho=rho[P_i], rhoerr=rhoerr[P_i], n=num[P_i]))
            
    # per P bin
    rho = rho / dp
    rhoerr = rhoerr / dp
            
    return rho, rhoerr, num


def get_rho_z(zbins, pbins, power, zmin, zmax, area, ind=None, verbose=True):
    '''
    pbins - bin of power (giving bin boundaries)
    power - log10(power) values
    zmin - for each source minimum z it could be observed (taking into account all selections)
    zmax - for each source maximum z it could be observed
    area - of survey in steradians
    ind - optically specify a selection index
    
    The differential comoving volume element dV_c/dz/dSolidAngle.
    Dimensions are volume per unit redshift per unit solid angle.
    Units are Mpc**3 Steradians^-1.
    '''
    print("Calculating LF: {n} sources".format(n=len(power)))
    if ind is not None:
        power = power[ind]
        zmin = zmin[ind]
        zmax = zmax[ind]
        print("sub-selected {n} sources".format(n=len(power)))
    
    # number of bins
    #N_P_bins = len(pbins) - 1
    N_z_bins = len(zbins) - 1
    
    # bin widths
    dp = pbins[1:] - pbins[:-1]
    
    rho  = np.nan*np.ones((N_z_bins))
    rhoerr  = np.nan*np.ones((N_z_bins))
    num   = np.nan*np.ones((N_z_bins))
    for P_i in range( N_z_bins ): #loop over log P
        # count  #
        sel_ind = np.where( (power > pbins[P_i])  & (power <= pbins[P_i + 1]) )[0]
        #powerhigh = pbins[P_i + 1]
        
        if len(sel_ind) > 1:  # at least 2
            zmax_h = zmax[sel_ind]
            zmin_h = zmin[sel_ind]
            
            vzmax = acosmo.comoving_volume(zmax_h).value
            vzmin = acosmo.comoving_volume(zmin_h).value
            
            vi = (vzmax - vzmin)*(area/(4.*np.pi))
            rho[P_i]  =  np.sum(1./vi)      #sum of 1/v_max for each source
            #rhoerr[P_i] =  rho[P_i]*np.sqrt(float(len(sel_ind)))/float(len(sel_ind))
            rhoerr[P_i] = np.sqrt(np.sum((1./vi)**2.))
            num[P_i]  =  float(len(sel_ind))
        if verbose:
            print("{p1:7.2f} < P <= {p2:6.2f} ({n:.0f}) : {rho:6.2e} +/- {rhoerr:6.2e}".format(p1=pbins[P_i], p2=pbins[P_i + 1], rho=rho[P_i], rhoerr=rhoerr[P_i], n=num[P_i]))
            
    # per P bin
    rho = rho / dp
    rhoerr = rhoerr / dp
            
    return rho, rhoerr, num


def get_CLF(pbins, power, zmin, zmax, area, ind=None, verbose=True):
    '''
    pbins - bins of power (giving bin boundaries)
    power - log10(power) values
    zmin - for each source minimum z it could be observed (taking into account all selections)
    zmax - for each source maximum z it could be observed
    area - of survey in steradians
    ind - optically specify a selection index
    
    The differential comoving volume element dV_c/dz/dSolidAngle.
    Dimensions are volume per unit redshift per unit solid angle.
    Units are Mpc**3 Steradians^-1.
    '''
    print("Calculating CLF: {n} sources".format(n=len(power)))
    if ind is not None:
        power = power[ind]
        zmin = zmin[ind]
        zmax = zmax[ind]
        print("sub-selected {n} sources".format(n=len(power)))
    
    # number of bins
    N_P_bins = len(pbins) - 1
    
    # bin widths
    dp = pbins[1:] - pbins[:-1]
    
    rho  = np.nan*np.ones((N_P_bins))
    rhoerr  = np.nan*np.ones((N_P_bins))
    num   = np.nan*np.ones((N_P_bins))
    for P_i in range( N_P_bins ): #loop over log P
        # count  #
        sel_ind = np.where( (power > pbins[P_i])  )[0]
        #powerhigh = pbins[P_i + 1]
        
        if len(sel_ind) > 0:
            zmax_h = zmax[sel_ind]
            zmin_h = zmin[sel_ind]
            
            vzmax = acosmo.comoving_volume(zmax_h).value
            vzmin = acosmo.comoving_volume(zmin_h).value
            
            vi = (vzmax - vzmin)*(area/(4.*np.pi))
            rho[P_i]  =  np.sum(1./vi)      #sum of 1/v_max for each source
            #rhoerr[P_i] =  rho[P_i]*np.sqrt(float(len(sel_ind)))/float(len(sel_ind))
            rhoerr[P_i] = np.sqrt(np.sum((1./vi)**2.))
            num[P_i]  =  float(len(sel_ind))
        if verbose:
            print("{p1:7.2f} < P ({n:.0f}) : {rho:6.2e} +/- {rhoerr:6.2e}".format(p1=pbins[P_i], rho=rho[P_i], rhoerr=rhoerr[P_i], n=num[P_i]))
            
    # per P bin
    rho = rho 
    rhoerr = rhoerr 
            
    return rho, rhoerr, num

def get_LF_f_areal(pbins_in, power, zmin, zmax, fcor, areal, area, ind=None, verbose=True, xstr="P", ignoreMinPower=False):
    '''
    pbins - bins of power (giving bin boundaries)
    power - log10(power) values
    zmin - for each source minimum z it could be observed (taking into account all selections)
    zmax - for each source maximum z it could be observed
    fcor - correction factor for completeness
    areal - the fractional areal coverage per source
    area - of survey in steradians
    ind - optically specify a selection index
    
    The differential comoving volume element dV_c/dz/dSolidAngle.
    Dimensions are volume per unit redshift per unit solid angle.
    Units are Mpc**3 Steradians^-1.
    '''
    pbins = pbins_in.copy()  # copy the pbins cos we're going to mess with them #
    #print pbins
    #print type(pbins)
    #print pbins_in
    #print type(pbins_in)
    print("Calculating {s}F (f_areal): {n} sources".format(n=len(power),s=xstr))
    if ind is not None:
        power = power[ind]
        zmin = zmin[ind]
        zmax = zmax[ind]
        fcor = fcor[ind]
        areal = areal[ind]
        print("sub-selected {n} sources".format(n=len(power)))
    
    minpower = np.min(power)
    
    # number of bins
    N_P_bins = len(pbins) - 1
    
    # bin widths
    dpnom = pbins[1:] - pbins[:-1]
    
    dp  = np.ones((N_P_bins)) * dpnom
    rho  = np.nan*np.ones((N_P_bins))
    rhoerr  = np.nan*np.ones((N_P_bins))
    num   = np.nan*np.ones((N_P_bins))
    for P_i in range( N_P_bins ): #loop over log P
        
    #for P_i in [5]: #loop over log P
        # count  #
        sel_ind = np.where( (power >= pbins[P_i])  & (power < pbins[P_i + 1]) )[0]
        if len(sel_ind) > 0:
        #powerhigh = pbins[P_i + 1]
        
        
            # discard the bin if the minimum value lies in this bin  - i.e. we are certainly not complete here #
            if not ignoreMinPower:
                if minpower > pbins[P_i]:
                    continue
                
            zmax_h = zmax[sel_ind]
            zmin_h = zmin[sel_ind]
            areal_h = areal[sel_ind]
            fcor_h = fcor[sel_ind]
            
            vzmax = acosmo.comoving_volume(zmax_h).value ## Mpc^3
            vzmin = acosmo.comoving_volume(zmin_h).value
            
            vi = (vzmax - vzmin)*(area/(4.*np.pi))  #area/4pi gives per sterad
            rho[P_i]  =  np.sum(fcor_h/(areal_h*vi))      #sum of 1/v_max for each source
            #rhoerr[P_i] =  rho[P_i]*np.sqrt(float(len(sel_ind)))/float(len(sel_ind))
            rhoerr[P_i] = np.sqrt(np.sum((fcor_h/(areal_h*vi))**2.))
            num[P_i]  =  float(len(sel_ind))
            #print vzmax.min(), vzmax.max()#, vzmax
            #print vzmin.min(), vzmin.max()#, vzmin
            #print vi.min(), vi.max()#, vzmin
            #print np.sum(1./vi)#, vzmin
        if verbose:
            print("{p1:7.2f} < {x} <= {p2:6.2f} ({n:.0f}) : {rho:6.2e} +/- {rhoerr:6.2e}".format(x=xstr, p1=pbins[P_i], p2=pbins[P_i + 1], rho=rho[P_i]/dp[P_i], rhoerr=rhoerr[P_i]/dp[P_i], n=num[P_i]))
            
    # per P bin
    rho = rho / dp
    rhoerr = rhoerr / dp
    
            
    return rho, rhoerr, num


def get_LF_rms_f_areal(pbins_in, power, Vzmin, Vzmax, fcor, areal, ind=None, verbose=True, xstr="P", ignoreMinPower=False):
    '''
    pbins - bins of power (giving bin boundaries)
    power - log10(power) values
    Vzmin - for each source minimum Vz it could be observed (taking into account all selections)  -- actual area, (i.e. fraction of full sky)
    Vzmax - for each source maximum Vz it could be observed
    fcor - correction factor for completeness
    areal - the fractional areal coverage per source
    ind - optically specify a selection index
    
    The differential comoving volume element dV_c/dz/dSolidAngle.
    Dimensions are volume per unit redshift per unit solid angle.
    Units are Mpc**3 Steradians^-1.
    '''
    pbins = pbins_in.copy()  # copy the pbins cos we're going to mess with them #
    #print pbins
    #print type(pbins)
    #print pbins_in
    #print type(pbins_in)
    print("Calculating {s}F (f_areal): {n} sources".format(n=len(power),s=xstr))
    if ind is not None:
        power = power[ind]
        Vzmin = Vzmin[ind]
        Vzmax = Vzmax[ind]
        fcor = fcor[ind]
        areal = areal[ind]
        print("sub-selected {n} sources".format(n=len(power)))
    
    minpower = np.min(power)
    
    # number of bins
    N_P_bins = len(pbins) - 1
    
    # bin widths
    dpnom = pbins[1:] - pbins[:-1]
    
    dp  = np.ones((N_P_bins)) * dpnom
    rho  = np.nan*np.ones((N_P_bins))
    rhoerr  = np.nan*np.ones((N_P_bins))
    num   = np.nan*np.ones((N_P_bins))
    for P_i in range( N_P_bins ): #loop over log P
        
    #for P_i in [5]: #loop over log P
        # count  #
        sel_ind = np.where( (power >= pbins[P_i])  & (power < pbins[P_i + 1]) )[0]
        if len(sel_ind) > 0:
        #powerhigh = pbins[P_i + 1]
        
        
            # discard the bin if the minimum value lies in this bin  - i.e. we are certainly not complete here #
            if not ignoreMinPower:
                if minpower > pbins[P_i]:
                    continue
                
            Vzmax_h = Vzmax[sel_ind]
            Vzmin_h = Vzmin[sel_ind]
            areal_h = areal[sel_ind]
            fcor_h = fcor[sel_ind]
            
            #vzmax = cosmo.distance.comoving_volume(zmax_h, **default_cosmo) ## Mpc^3
            #vzmin = cosmo.distance.comoving_volume(zmin_h, **default_cosmo)
            
            #vi = (Vzmax_h - Vzmin_h)*(area/(4.*np.pi))  #area/4pi gives per sterad
            vi = (Vzmax_h - Vzmin_h) #*(domega/(4.*np.pi))  #area/4pi gives per sterad
            vi[vi <= 0] = np.nan
            rho[P_i]  =  np.nansum(fcor_h/(areal_h*vi))      #sum of 1/v_max for each source
            #rhoerr[P_i] =  rho[P_i]*np.sqrt(float(len(sel_ind)))/float(len(sel_ind))
            rhoerr[P_i] = np.sqrt(np.nansum((fcor_h/(areal_h*vi))**2.))
            num[P_i]  =  float(len(sel_ind))
            #print vzmax.min(), vzmax.max()#, vzmax
            #print vzmin.min(), vzmin.max()#, vzmin
            #print vi.min(), vi.max()#, vzmin
            #print np.sum(1./vi)#, vzmin
            #if np.isnan(rho[P_i]):
                #print 'Num is nan:', num[P_i]
                #print Vzmax_h
                #print Vzmin_h
        if verbose:
            print("{p1:7.2f} < {x} <= {p2:6.2f} ({n:.0f}) : {rho:6.2e} +/- {rhoerr:6.2e}".format(x=xstr, p1=pbins[P_i], p2=pbins[P_i + 1], rho=rho[P_i]/dp[P_i], rhoerr=rhoerr[P_i]/dp[P_i], n=num[P_i]))
            
    # per P bin
    rho = rho / dp
    rhoerr = rhoerr / dp
    #if np.any(rho < 0):
        #import ipdb
        #ipdb.set_trace()
            
    return rho, rhoerr, num


def get_CLF_f_areal(pbins, power, zmin, zmax, fcor, areal, domega, ind=None, verbose=True, xstr="P"):
    '''
    pbins - bins of power (giving bin boundaries)
    power - log10(power) values
    zmin - for each source minimum z it could be observed (taking into account all selections)
    zmax - for each source maximum z it could be observed
    fcor - correction factor for completeness
    areal - the fractional areal coverage per source
    domega - of survey in steradians
    ind - optically specify a selection index
    
    The differential comoving volume element dV_c/dz/dSolidAngle.
    Dimensions are volume per unit redshift per unit solid angle.
    Units are Mpc**3 Steradians^-1.
    '''
    print("Calculating CLF (f_areal): {n} sources".format(n=len(power)))
    if ind is not None:
        power = power[ind]
        zmin = zmin[ind]
        zmax = zmax[ind]
        fcor = fcor[ind]
        areal = areal[ind]
        print("sub-selected {n} sources".format(n=len(power)))
    
    minpower = np.min(power)
    
    # number of bins
    N_P_bins = len(pbins) - 1
    
    # bin widths
    dp = pbins[1:] - pbins[:-1]
    
    rho  = np.nan*np.ones((N_P_bins))
    rhoerr  = np.nan*np.ones((N_P_bins))
    num   = np.nan*np.ones((N_P_bins))
    for P_i in range( N_P_bins ): #loop over log P
        
        # discard the bin if the minimum value lies in this bin  - i.e. we are certainly not complete here #
        if minpower > pbins[P_i]:
            continue
        # count  #
        sel_ind = np.where( (power >= pbins[P_i])  )[0]
        #powerhigh = pbins[P_i + 1]
        
        if len(sel_ind) > 0:
            zmax_h = zmax[sel_ind]
            zmin_h = zmin[sel_ind]
            areal_h = areal[sel_ind]
            fcor_h = fcor[sel_ind]
            
            vzmax = acosmo.comoving_volume(zmax_h).value
            vzmin = acosmo.comoving_volume(zmin_h).value
            
            vi = (vzmax - vzmin)*(domega/(4.*np.pi))  #area/4pi gives per sterad
            rho[P_i]  =  np.sum(fcor_h/(areal_h*vi))      #sum of 1/v_max for each source
            #rhoerr[P_i] =  rho[P_i]*np.sqrt(float(len(sel_ind)))/float(len(sel_ind))
            rhoerr[P_i] = np.sqrt(np.sum((fcor_h/(areal_h*vi))**2.))
            num[P_i]  =  float(len(sel_ind))
        if verbose:
            print("{x} > {p1:7.2f} ({n:.0f}) : {rho:6.2e} +/- {rhoerr:6.2e}".format(x=xstr, p1=pbins[P_i], rho=rho[P_i], rhoerr=rhoerr[P_i], n=num[P_i]))
            
    # per P bin - no, this is CLF
    rho = rho #/ dp
    rhoerr = rhoerr #/ dp
            
    return rho, rhoerr, num


def get_rho_Plim_f_areal(plimit, power, zmin, zmax, fcor, areal, domega, ind=None, verbose=True, xstr="P"):
    '''
    plimit - bins of power (giving bin boundaries)
    power - log10(power) values
    zmin - for each source minimum z it could be observed (taking into account all selections)
    zmax - for each source maximum z it could be observed
    fcor - correction factor for completeness
    areal - the fractional areal coverage per source
    domega - of survey in steradians
    ind - optically specify a selection index
    
    The differential comoving volume element dV_c/dz/dSolidAngle.
    Dimensions are volume per unit redshift per unit solid angle.
    Units are Mpc**3 Steradians^-1.
    '''
    print("Calculating density above power limit (f_areal): {n} sources".format(n=len(power)))
    if ind is not None:
        power = power[ind]
        zmin = zmin[ind]
        zmax = zmax[ind]
        fcor = fcor[ind]
        areal = areal[ind]
        print("sub-selected {n} sources".format(n=len(power)))
    
    
    rho  = np.nan
    rhoerr  = np.nan
    num   = np.nan
    
    minpower = np.min(power)
    if minpower > plimit:
        print(" missing sources between {p2:.2f} and {p1:.2f}".format(p1=minpower, p2=plimit))
        return rho, rhoerr, num
        
    sel_ind = np.where( (power >= plimit)  )[0]
    #powerhigh = pbins[P_i + 1]
    
    if len(sel_ind) > 0:
        zmax_h = zmax[sel_ind]
        zmin_h = zmin[sel_ind]
        areal_h = areal[sel_ind]
        fcor_h = fcor[sel_ind]
        
        vzmax = cosmo.comoving_volume(zmax_h).value
        vzmin = cosmo.comoving_volume(zmin_h).value
        
        vi = (vzmax - vzmin)*(domega/(4.*np.pi))  #area/4pi gives per sterad
        rho  =  np.sum(fcor_h/(areal_h*vi))      #sum of 1/v_max for each source
        #rhoerr[P_i] =  rho[P_i]*np.sqrt(float(len(sel_ind)))/float(len(sel_ind))
        rhoerr = np.sqrt(np.sum((fcor_h/(areal_h*vi))**2.))
        num  =  float(len(sel_ind))
    if verbose:
        print("{x} > {p1:7.2f} ({n:.0f}) : {rho:6.2e} +/- {rhoerr:6.2e}".format(x=xstr, p1=plimit, rho=rho, rhoerr=rhoerr, n=num))
            
    ## per P bin - nope this is > plimit
    #rho = rho #/ dp
    #rhoerr = rhoerr #/ dp
            
    return rho, rhoerr, num


def vmax_arr(m,z,mlim,area):
    '''
    vmax for array input
    '''
    N = len(m)
    if len(z) != N:
        print('mismatch in input array sizes, m and z must be same length')
        return
    Avmax = np.nan*np.zeros(N)
    for i in range(N):
        Avmax[i] = vmax(m[i],z[i],mlim,area)
    return Avmax
    
def count_in_bins(xbins,xdata, norm=False):
    '''
    count_in_bins : histogram with errors
     input - xbins : array of x bins
             xdata : data to bin
    output - xmidrange : midpoints of bins
                nrange : counts per bin
               enrange : errors per bin [Poissonian] 
    '''
    nbins = len(xbins)-1
    nrange = np.zeros(nbins)
    enrange = np.zeros(nbins)
    xmidrange = np.zeros(nbins)
    for xi in range(nbins):
        xmidrange[xi] = 0.5*(xbins[xi] + xbins[xi+1])
        # count xdata between xi and xi+1
        nrange[xi] = np.sum((xdata>=xbins[xi])*(xdata<xbins[xi+1]) )
        enrange[xi] = np.sqrt(nrange[xi])
    # normalise:
    # note things outside the range covered will NOT be counted in the normalisation
    if norm:
        nF = 1./np.sum(nrange)
        nrange = nF*nrange
        enrange = nF*enrange
    
    return xmidrange, nrange, enrange
    
    
def sum_in_bins(xbins,xdata, ydata, norm=False):
    '''
    sum_in_bins : histogram with errors
     input - xbins : array of x bins
             xdata : data for bins
             ydata : data to sum in each x bin
    output - xmidrange : midpoints of bins
                nrange : counts per bin
               enrange : errors per bin [Poissonian] 
    '''
    nbins = len(xbins)-1
    Srange = np.zeros(nbins)
    eSrange = np.zeros(nbins)
    xmidrange = np.zeros(nbins)
    for xi in range(nbins):
        xmidrange[xi] = 0.5*(xbins[xi] + xbins[xi+1])
        # count xdata between xi and xi+1
        N = np.sum((xdata>=xbins[xi])*(xdata<xbins[xi+1]) )
        Srange[xi] = np.sum(ydata*(xdata>xbins[xi])*(xdata<xbins[xi+1]) )
        eSrange[xi] = Srange[xi] * np.sqrt(N)
    # normalise:
    # note things outside the range covered will NOT be counted in the normalisation
    if norm:
        nF = 1./np.sum(Srange)
        Srange = nF*Srange
        eSrange = nF*eSrange
    
    return xmidrange, Srange, eSrange


