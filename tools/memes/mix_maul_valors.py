"""Sound mix for maul_valors. Times match tools/memes/maul_valors.py (video 6.0 s, held 0.8 s at the end for the boom).

python3 tools/memes/mix_maul_valors.py <out.wav>
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mixlib import *

DUR = 6.8
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'extract/memes/maul_valors.wav')
init(DUR)

RISE = [0.7, 1.15, 1.6, 2.05, 2.5]
PAN = [-0.85, -0.42, 0.0, 0.42, 0.85]
JIT = [0.98, 1.03, 0.96, 1.01, 1.05]

# beds: idling engines, then five Valors breathing heavily at Maul
loop('veh_ram_mvt_engine_idle_loop_01', 0, DUR, lambda t: -24)
loop('veh_healer_mvt_engine_idle_loop_01', 0.7, DUR, lambda t: -30 + 6 * ramp(t, 0.7, 2.9))
loop('breathing_heavy', 2.9, DUR, lambda t: -40 + 27 * ramp(t, 2.9, 3.4), pan_fn=lambda t: -0.35)
loop('breathing_heavy2', 3.1, DUR, lambda t: -40 + 25 * ramp(t, 3.1, 3.6), pan_fn=lambda t: 0.4, trim=(1.0, None))

# each Valor pops up into its handstand, calls out Maul
for i, t in enumerate(RISE):
    place('boing_harp', t + 0.04, -9, rate=0.8 + 0.1 * i, pan=PAN[i])
    place(f'veh_med_mvt_sus_shock_base_0{1 + i}', t + 0.3, -9, pan=PAN[i])
    place(f'VO_Healer_Base_Spotting{1 + i}', t + 0.18, -5, rate=JIT[i], pan=PAN[i])
# five guns swing down onto Maul
for i in range(5):
    place(f'veh_healer_mvt_turn_start_0{1 + i % 3}', 2.75 + 0.08 * i, -11, pan=PAN[i])
    place(f'veh_healer_mvt_turn_stop_0{1 + i % 3}', 3.2 + 0.08 * i, -11, pan=PAN[i])

# Maul: nervous glances up right, up left, a gulp, then deadpan into the camera - boom
place('veh_ram_mvt_turn_start_01', 3.28, -9, pan=0.1)
place('VO_Ram_Base_Spotted4', 3.45, -4)
place('veh_ram_mvt_turn_start_02', 3.98, -9, pan=-0.1)
place('gulp_cartoon', 4.42 - 0.55, -3)
place('veh_ram_mvt_turn_stop_01', 4.5, -9)
place('bass_impact', 4.72, 0, fade_out=0.6)
place('boom_impact2', 4.72, -7, fade_out=0.5)

write(OUT)
print('wrote', OUT, f'{DUR}s')
