"""Sound mix for chase_fields. Times match tools/memes/chase_fields.py; the flush starts at 12.6 s.

python3 tools/memes/mix_chase_fields.py <out.wav> [nomusic]
'nomusic' leaves the music out so the owner can lay Yakkety Sax (or anything) over it in an editor.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mixlib import *

DUR = 15.0
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'extract/memes/chase_fields.wav')
MUSIC = not (len(sys.argv) > 2 and sys.argv[2] == 'nomusic')
init(DUR)
T_GO, T_STOP, T_SPIN0, T_SPIN1, T_BACK, T_FLUSH = 0.3, 6.6, 7.0, 7.9, 8.4, 12.6
PAN = [0.6, 0.4, 0.2, 0.0, -0.15, -0.3, -0.45, -0.6]

if MUSIC:   # the rag, sped up; cuts dead on the screech, comes back faster for the chase the other way
    R1, R2 = 1.12, 1.22
    place('ragtime_eashby', 0.0, 0, trim=(0, T_STOP * R1), rate=R1, fade_out=0.02)
    place('ragtime_eashby', T_BACK, 0, trim=(T_STOP * R1, T_STOP * R1 + (T_FLUSH + 0.8 - T_BACK) * R2), rate=R2, fade_in=0.01, fade_out=0.7)

running = lambda t: ramp(t, T_GO, T_GO + 0.4) * (1 - ramp(t, T_STOP, T_STOP + 0.3)) + ramp(t, T_BACK, T_BACK + 0.3) * (1 - ramp(t, T_FLUSH, T_FLUSH + 1.0))
loop('veh_shared_mvt_engine_active_loop_pitched_01', 0, DUR, lambda t: -40 + 24 * running(t), rate_fn=lambda t: 1.0 + 0.6 * running(t) + (0.15 if t > T_BACK else 0))
loop('veh_blink_mvt_engine_active_loop_pitched_01', 0, DUR, lambda t: -40 + 22 * running(t), rate_fn=lambda t: 1.2 + 0.5 * running(t), pan_fn=lambda t: 0.3)
loop('veh_shared_mvt_engine_idle_loop_01', 0, DUR, lambda t: -26 + 6 * (1 - running(t)) - 30 * ramp(t, T_FLUSH, T_FLUSH + 1.2))
place('veh_blink_mvt_engine_start_01', 0.0, -10, length=1.5, fade_out=0.4)
place('zip_in_out', T_GO - 0.1, -9, trim=(0, 1.0), fade_out=0.2)

# screech to a stop
for i, n in enumerate(('veh_shared_mvt_handbrake_dust_01', 'veh_shared_mvt_handbrake_dust_02', 'veh_shared_mvt_handbrake_dust_03')):
    place(n, T_STOP + 0.02 * i, -4, pan=(-0.4, 0.0, 0.4)[i])
place('veh_sonar_mvt_turn_stop_01', T_STOP + 0.1, -8)
place('veh_ram_mvt_turn_stop_02', T_STOP + 0.15, -8, pan=-0.2)
# everyone spins round
for i in range(8):
    place('swoosh_fast', T_SPIN0 + 0.06 * i - 1.15, -14, trim=(0.9, 1.6), pan=PAN[i], rate=1.0 + 0.04 * i)
# "uh oh": the Valors now lead, so they're the ones running away
place('VO_Healer_Base_PingRetreat1', T_SPIN1 + 0.0, -4, pan=-0.4)
place('VO_Healer_Base_PingRetreat2', T_SPIN1 + 0.25, -6, pan=-0.6, rate=1.05)
place('VO_Blink_Base_RamEnemy3', T_BACK - 0.2, -3, pan=0.6)
place('zip_in_out', T_BACK - 0.15, -8, trim=(0, 1.0), fade_out=0.2)

# flush
place('toilet_flush', T_FLUSH - 0.1, -1)
place('toilet_flush2', T_FLUSH + 0.6, -8, trim=(0, 2.4), fade_out=0.8)

write(OUT)
print('wrote', OUT, f'{DUR}s', 'music' if MUSIC else 'no music')
