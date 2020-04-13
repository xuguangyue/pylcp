"""
author:spe

This little script tests the optical pumping from the optical Bloch equations
and rate equations.  It reproduces Fig. 5 of Ungar, P. J., Weiss, D. S., Riis,
E., & Chu, S. (1989). Optical molasses and multilevel atoms: theory. Journal of
the Optical Society of America B, 6(11), 2058.
http://doi.org/10.1364/JOSAB.6.002058

There seems to be at least a factor of 2 pi missing in the above paper.

Note that agreement will only occur with the rate equations in the case of
a single laser beam.  This is because the rate equations assume that the
lasers are incoherent (their electric fields do not add to give twice the
amplitude) whereas the optical bloch equations do.
"""
import numpy as np
import matplotlib.pyplot as plt
import pylcp
from pylcp.common import spherical2cart
from scipy.integrate import solve_ivp
import time
plt.style.use('paper')

# %%
"""
Let's start by checking rotations by optically pumping with circular polarized
light along all three axes and seeing if it pumps to the appropriate spin state
along those axes.

We will do this in multiple ways.  The first is to construct the Hamiltonian
directly, the second is
"""
# Which polarization do we want?
pol = +1

# First, create the laser beams:
laserBeams = {}
laserBeams['x']= pylcp.laserBeams([
    {'kvec': np.array([1., 0., 0.]), 'pol':pol, 'delta':0., 'beta':2.0}
    ])
laserBeams['y']= pylcp.laserBeams([
    {'kvec': np.array([0., 1., 0.]), 'pol':pol, 'delta':0., 'beta':2.0}
    ])
laserBeams['z']= pylcp.laserBeams([
    {'kvec': np.array([0., 0., 1.]), 'pol':pol, 'delta':0., 'beta':2.0}
    ])

# For making the Hamiltonian
E={}
for key in laserBeams:
    E[key] = laserBeams[key].cartesian_pol()[0]

# Then the magnetic field:
magField = lambda R: np.zeros(R.shape)
gF=1
# Hamiltonian for F=0->F=1
Hg, mugq, basis_g = pylcp.hamiltonians.singleF(F=0, gF=gF, muB=1, return_basis=True)
He, mueq, basis_e = pylcp.hamiltonians.singleF(F=1, gF=gF, muB=1, return_basis=True)
d_q = pylcp.hamiltonians.dqij_two_bare_hyperfine(0, 1)
hamiltonian = pylcp.hamiltonian(Hg, He, mugq, mueq, d_q)
laserBeams['x'].total_electric_field(np.array([0., 0., 0.]), 0.)
obe = {}

basis =np.concatenate((basis_g, basis_e))

# Excited state spin observable.  The spin is not along the
S_ex = -spherical2cart(mueq)/gF

fig, ax = plt.subplots(3, 2, figsize=(6.5, 2.5*2.75))
for ii, key in enumerate(laserBeams):
    # In this loop, we will make the
    ax[ii, 1].plot(np.linspace(0, 4*np.pi, 51),
                   pol*(1-np.cos(np.linspace(0, 4*np.pi, 51)))/2, 'k-',
                   linewidth=1)
    d = spherical2cart(d_q)
    H_sub = -0.5*np.tensordot(d, E[key], axes=(0, 0))

    H = np.zeros((4, 4)).astype('complex128')
    H[0, 1:] = H_sub
    H[1:, 0] = np.conjugate(H_sub)

    H_sub2 = np.zeros(d_q[0].shape).astype('complex128')
    for kk, q in enumerate(np.arange(-1, 2, 1)):
        H_sub2 -= 0.5*(-1.)**q*d_q[kk]*laserBeams[key].beam_vector[0].pol[2-kk]

    H2 = np.zeros((4, 4)).astype('complex128')
    H2[0, 1:] = H_sub2
    H2[1:, 0] = np.conjugate(H_sub2)

    H3 = hamiltonian.return_full_H({'g->e': laserBeams[key].beam_vector[0].pol},
                                   np.zeros((3,)).astype('complex128'))
    psi0 = np.zeros((4,)).astype('complex128')
    psi0[0] = 1.
    sol = solve_ivp(lambda t, x: -1j*H2 @ x, [0, 4*np.pi], psi0,
                    t_eval=np.linspace(0, 4*np.pi, 51))

    print(np.allclose(H, H2), np.allclose(H, H3))

    S_av = np.zeros(sol.t.shape)
    for jj in range(sol.t.size):
        S_av[jj] = np.conjugate(sol.y[1:, jj])@S_ex[ii]@sol.y[1:, jj]

    for jj in range(4):
        ax[ii, 0].plot(sol.t, np.abs(sol.y[jj, :])**2, '--', color='C%d'%jj)

    ax[ii, 1].plot(sol.t, S_av, '--')

    obe[key] = pylcp.obe(laserBeams[key], magField, hamiltonian,
                         transform_into_re_im=False)
    rho0 = np.zeros((16,))
    rho0[0] = 1 # Always start in the ground state.

    obe[key].ev_mat['decay'][:, :] = 0. # Forcibly turn off decay, make it like S.E.
    obe[key].set_initial_rho(rho0)
    obe[key].evolve_density(t_span=[0, 2*np.pi*2], t_eval=np.linspace(0, 4*np.pi, 51))

    (t, rho) = obe[key].reshape_sol()

    for jj in range(4):
        ax[ii, 0].plot(t, np.real(rho[jj, jj]), linewidth=0.75, color='C%d'%jj,
                       label='$|%d,%d\\rangle$'%(basis[jj, 0], basis[jj, 1]))
    ax[ii, 0].set_ylabel('$\\rho_{ii}$')

    S_av = np.zeros(t.shape)
    for jj in range(t.size):
        S_av[jj] = np.real(np.sum(np.sum(S_ex[ii]*rho[1:, 1:, jj])))

    ax[ii, 1].plot(t, S_av, linewidth=0.75)
    ax[ii, 1].set_ylabel('$\\langle S_%s\\rangle$'%key)

[ax[-1, jj].set_xlabel('$\Gamma t$') for jj in range(2)]
ax[0, 0].legend()
fig.subplots_adjust(left=0.08, bottom=0.05, wspace=0.22)

# %%
"""
Next, let's apply a magnetic field and see if we can tune the lasers into
resonance.  This will check to make sure that we have the detunings right.

With g_F>0, the shift for +m_F is downwards.
"""
magField = {}
magField['x'] = lambda R: np.array([+1., 0., 0.])
magField['y'] = lambda R: np.array([0., +1., 0.])
magField['z'] = lambda R: np.array([0., 0., +1.])

pol=+1
laser_det=-1
ham_det=0.
laserBeams = {}
laserBeams['x']= pylcp.laserBeams([
    {'kvec': np.array([1., 0., 0.]), 'pol':pol, 'delta':laser_det, 'beta':2.0}
    ])
laserBeams['y']= pylcp.laserBeams([
    {'kvec': np.array([0., 1., 0.]), 'pol':pol, 'delta':laser_det, 'beta':2.0}
    ])
laserBeams['z']= pylcp.laserBeams([
    {'kvec': np.array([0., 0., 1.]), 'pol':pol, 'delta':laser_det, 'beta':2.0}
    ])

fig, ax = plt.subplots(3, 2, figsize=(6.5, 2.5*2.75))
for ii, key in enumerate(laserBeams):
    obe[key] = pylcp.obe(laserBeams[key], magField[key], hamiltonian,
                         transform_into_re_im=False)
    rho0 = np.zeros((16,))
    rho0[0] = 1 # Always start in the ground state.

    obe[key].ev_mat['decay'][:, :] = 0. # Forcibly turn off decay, make it like S.E.
    obe[key].set_initial_rho(rho0)
    obe[key].evolve_density(t_span=[0, 2*np.pi*2], t_eval=np.linspace(0, 4*np.pi, 51))

    (t, rho) = obe[key].reshape_sol()

    for jj in range(4):
        ax[ii, 0].plot(t, np.real(rho[jj, jj]), linewidth=0.75, color='C%d'%jj)

    S_av = np.zeros(t.shape)
    for jj in range(t.size):
        S_av[jj] = np.real(np.sum(np.sum(S_ex[ii]*rho[1:, 1:, jj])))

    ax[ii, 1].plot(t, S_av, linewidth=0.75)


# %%
"""
Let's now re-define the problem to match the Ungar paper.  Note that one can
put the detuning on the laser or put the detuning on the Hamiltonian.
The latter is faster.
"""
# First the laser beams:
laserBeams = {}
laserBeams['x']= pylcp.laserBeams([
    {'kvec': np.array([1., 0., 0.]), 'pol':np.array([0., 0., 1.]),
     'delta':-2.73, 'beta':4*0.16}
    ])
"""laserBeams.append(pylcp.laserBeam(np.array([-1., 0., 0.]),
                                  pol=np.array([0., 0., 1.]),
                                  delta=-2.73, beta=lambda k, R: 0.16))"""
laserBeams['z']= pylcp.laserBeams([
    {'kvec': np.array([0., 0., 1.]), 'pol':np.array([0., 1., 0.]),
     'delta':-2.73, 'beta':4*0.16}
    ])

# Then the magnetic field:
magField = lambda R: np.zeros(R.shape)

# Hamiltonian for F=2->F=3
Hg, mugq = pylcp.hamiltonians.singleF(F=2, gF=1, muB=1)
He, mueq = pylcp.hamiltonians.singleF(F=3, gF=1, muB=1)
dijq = pylcp.hamiltonians.dqij_two_bare_hyperfine(2, 3)
hamiltonian = pylcp.hamiltonian(Hg, He-0.*np.eye(He.shape[0]),
                                mugq, mueq, dijq)
hamiltonian.print_structure()
# 0.16/2*1/(1+4*2.73**2)*dijq[1,0,1]**2


# %% Now, let's compute the optical pumping based on the rate equations:
rateeq = pylcp.rateeq(laserBeams['x'], magField, hamiltonian)



fig, ax = plt.subplots(1, 1)
for jj in range(5):
    ax.plot(rateeq.sol.t/2/np.pi, rateeq.sol.y[jj,:], '-', color='C{0:d}'.format(jj),
            linewidth=0.5)
ax.set_xlabel('$t/(2\pi\Gamma)$')
ax.set_ylabel('$\\rho_{ii}$')

# %%
"""
Now try the optical Bloch equations, first with the polarization along z:
"""
obe = {}
obe['z'] = pylcp.obe(laserBeams['x'], magField, hamiltonian,
                 transform_into_re_im=False)

N0 = np.zeros((obe['z].rateeq.hamiltonian.n,))
N0[0] = 1
obe['z].rateeq.set_initial_pop(N0)
obe['z].rateeq.evolve_populations([0, 2*np.pi*600])

rho0 = np.zeros((obe['z'].hamiltonian.n**2,))
rho0[0] = 1.
obe['z'].set_initial_rho(np.real(rho0))
tic = time.time()
obe['z'].evolve_density(t_span=[0, 2*np.pi*600])
toc = time.time()
print('Computation time is  %.2f s.' % (toc-tic))

(t, rho1) = obe['z'].reshape_sol()
for jj in range(5):
    ax.plot(t/2/np.pi, np.abs(rho1[jj, jj]), '--',
            color='C{0:d}'.format(jj),
            linewidth=0.5)
fig

# %%
"""
Next, we want to check that our rotations are working properly, so we will
run the same calculation for the z going beam with pi_y polarization.
"""
obe = {}
obe['pi_y'] = pylcp.obe(laserBeams['x'], magField, hamiltonian,
                 transform_into_re_im=False)
mug = spherical2cart(mugq)
S = -mug

# What are the eigenstates of 'y'?
E, U = np.linalg.eig(S[1])

inds = np.argsort(E)
E = E[inds]
U = U[:, inds]

# Start with the wavefunction U=-E.
psi = U[:, 4]

rho_g =
for ii in range(hamiltonian.ns[0]):
    for jj in range(hamiltonian.ns[0]):
        rho_g[ii, jj] = psi[ii]*np.conjugate(psi[jj])

# %% Now try the optical Bloch equations, using the obe, transformed into Re/Im.
obe2 = pylcp.obe(laserBeams, magField, hamiltonian,
                 transform_into_re_im=True)
obe2.set_initial_rho(np.real(rho0))
tic = time.time()
obe2.evolve_density(t_span=[0, 2*np.pi*600], method='RK45')
toc = time.time()
print('Computation time is  %.2f s.' % (toc-tic))

(t, rho2) = obe2.reshape_sol()
for jj in range(5):
    ax.plot(t/2/np.pi, np.abs(rho2[jj, jj]), '-.',
            color='C{0:d}'.format(jj),
            linewidth=0.5)
fig

# %% Add the end points game:
Neq = rateeq.equilibrium_populations(np.array([0., 0., 0.]),
                                     np.array([0., 0., 0.]), 0.)

for jj in range(5):
    ax.plot(obe1.sol.t[-1]/2/np.pi,
            Neq[jj], '.',
            color='C{0:d}'.format(jj),
            linewidth=0.5)
fig
