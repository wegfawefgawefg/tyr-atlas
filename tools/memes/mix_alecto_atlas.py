"""Sound mix for alecto_atlas: game sounds (extract/audio_wav, from `extract.dll audio` + vgmstream) and CC0 clips
(tools/memes/sounds, see CREDITS.txt) laid on the animation's timeline. Times match tools/memes/alecto_atlas.py.

python3 tools/memes/mix_alecto_atlas.py <out.wav>
"""
import sys, os, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mixlib import *
import mixlib

DUR = 9.5
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'extract/memes/alecto_atlas.wav')
init(DUR)

# ---- the same timeline numbers as alecto_atlas.py ----
T_ORBIT, T_SETTLE, T_HUMP, T_FLIP, T_KISS, T_CIG = 0.45, 2.0, 2.6, 4.7, 5.3, 6.0
OMEGA = 2 * math.pi * 2.5 / (T_SETTLE - T_ORBIT); RAD = 11.0; SETTLE_LEN = T_HUMP - T_SETTLE
PHI2 = math.pi - OMEGA * SETTLE_LEN / 2
def phi(t):
    if t <= T_SETTLE: return PHI2 - OMEGA * (T_SETTLE - t)
    tau = min(t - T_SETTLE, SETTLE_LEN); return PHI2 + OMEGA * tau - OMEGA * tau * tau / (2 * SETTLE_LEN)
CAM = np.array([-1, 0, 1.5]) + np.array([0.2, -1, 0.8]) / np.linalg.norm([0.2, -1, 0.8]) * 40
def alecto_xy(t):
    p = phi(t); yaw = p + math.pi / 2; pos = np.array([-1 + RAD * math.cos(p), RAD * math.sin(p), 1.6])
    if t < T_ORBIT: pos = pos - np.array([math.cos(yaw), math.sin(yaw), 0]) * OMEGA * RAD * (T_ORBIT - t)
    return pos
def orbit_dist(t): return np.linalg.norm(alecto_xy(t) - CAM)
def orbit_pan(t): return float(np.clip((alecto_xy(t)[0] + 1) / 16, -0.9, 0.9))
def doppler(t):
    v = (orbit_dist(t + 0.01) - orbit_dist(t - 0.01)) / 0.02; return float(np.clip(343 / (343 + v * 0.8), 0.75, 1.35))

def thrusts():
    """Contact times: psi = 2pi(2.4u + 0.65u^2) hits pi(2k+1)."""
    out = []; k = 0
    while True:
        u = (-2.4 + math.sqrt(2.4 ** 2 + 4 * 0.65 * (k + 0.5))) / (2 * 0.65); t = T_HUMP + u
        if t >= T_FLIP: return out
        if t > T_HUMP + 0.15: out.append(t)
        k += 1

# ---- beds ----
loop('veh_sonar_mvt_engine_idle_loop_01', 0, DUR, lambda t: -20 + 3 * ramp(t, 2.6, 3.2) - 3 * ramp(t, 4.8, 5.4), pan_fn=lambda t: -0.1)
loop('veh_sonar_mvt_engine_active_loop_pitched_01', 2.6, 5.0, lambda t: -22 + 8 * ramp(t, 2.6, 4.4) - 30 * ramp(t, 4.6, 5.0),
     rate_fn=lambda t: 1.0 + 0.35 * ramp(t, 2.8, 4.6))                       # Atlas revs up while it gets humped
loop('veh_blink_mvt_engine_active_loop_pitched_01', 0.0, 2.8,
     lambda t: -6 - 20 * math.log10(max(orbit_dist(t), 10) / 30) - 30 * ramp(t, 2.3, 2.8) - 20 * (1 - ramp(t, 0.0, 0.25)),
     rate_fn=lambda t: doppler(t) if t < T_SETTLE else doppler(T_SETTLE) * (1 - 0.3 * ramp(t, 2.0, 2.6)), pan_fn=orbit_pan)
loop('veh_blink_mvt_engine_idle_loop_01', 2.4, DUR, lambda t: -19 + 4 * ramp(t, 4.7, 5.0) - 4 * ramp(t, 5.3, 5.8),
     pan_fn=lambda t: -0.6 + 1.1 * ramp(t, 4.7, 5.3))
loop('veh_sonar_mvt_turn_loop_01', 0.6, 2.9, lambda t: -16 - 25 * ramp(t, 2.5, 2.9) - 20 * (1 - ramp(t, 0.6, 0.9)))   # dizzy turret

# ---- orbit ----
place('whoosh_electronic', 0.08, -4, pan=-0.8)
p_prev = phi(T_ORBIT)
for t in np.arange(T_ORBIT, T_SETTLE + 0.3, 0.005):          # a swoosh every time Alecto passes closest to the camera
    if math.floor((phi(t) + math.pi / 2) / (2 * math.pi)) != math.floor((p_prev + math.pi / 2) / (2 * math.pi)):
        place('swoosh_fast', t - 1.2, -7, pan=0.0)
    p_prev = phi(t)
place('wolf_whistle', 0.55, -7, pan=0.3)
place('VO_Sonar_Base_Spotted1', 0.85, -3)
place('veh_blink_mvt_turn_stop_01', 2.15, -6, pan=-0.6)       # skid in behind
place('veh_sonar_mvt_turn_stop_01', 2.75, -10)

# ---- hump ----
place('VO_Blink_Base_RamEnemy1', 2.62, -3, pan=-0.5)
for i, t in enumerate(thrusts()):
    place('squeaky_bed', t - 0.06, -5 + min(i, 6) * 0.4, trim=(1.02, 1.42), fade_out=0.08, rate=1.0 + 0.025 * i, pan=-0.35)
    place(f'veh_lrg_mvt_sus_shock_base_0{1 + i % 6}', t - 0.01, -10, pan=-0.3)
    place(f'veh_shared_collision_impact_nodamage_small_0{1 + i % 6}', t, -14 + min(i, 8), pan=-0.4)
place('moan_female4b', 2.75, -4, trim=(6.0, 8.25), fade_in=0.25, fade_out=0.15, pan=-0.45)
place('veh_sonar_special_activate_01', 3.0, -9)                 # radar spins up
place('boing_harp', 3.35, -6, rate=0.75, pan=-0.2)              # antennas extend
place('moan_m', 3.75, -6, pan=0.1)
place('oh_yeah_low', 4.25, -1, pan=0.05)                        # Atlas, barrel all the way up
place('veh_shared_horn_01', 4.55, -8)

# ---- leap and kiss ----
place('slide_whistle', 4.62, -6, trim=(0.45, 2.1), rate=1.6, fade_out=0.15)
place('toon_spin_swoosh', 4.75, -12, trim=(2.6, 3.4), fade_in=0.05, fade_out=0.2)
place('moan_iloveyou', 5.25, -5, pan=0.3)
place('kiss12', 5.47 - 0.5, -2, pan=0.15)
place('kiss_short', 5.64, -4, pan=0.15)
place('chime_gleam', 5.55 - 1.45, -12, trim=(1.2, 3.6), fade_out=0.6)

# ---- cigarette ----
place('poof_pop4', 5.98, -5, trim=(0.0, 0.9))
place('flash_powder', 6.0 - 0.55, -9)
place('sax_riff_2a', 6.15, -15, fade_in=0.6, fade_out=0.8, length=DUR - 6.15)
place('VO_Blink_Base_Victory1', 6.3, -7, pan=0.6)
place('zippo_open', 6.32 - 0.1, -9, pan=-0.1)
place('lighter_flick', 6.48, -8, pan=-0.1)
place('cig_drag', 6.62 - 0.2, -2, trim=(0, 1.9), fade_out=0.2)
place('exhale_blow', 7.2, -5, trim=(0.1, 2.3), fade_out=0.7)
place('VO_Sonar_Base_PingThanks1', 8.35, -3)

write(OUT)
print('wrote', OUT, f'{DUR}s', 'thrusts', [round(t, 2) for t in thrusts()])
