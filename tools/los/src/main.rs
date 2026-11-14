//! Spotting sweep for Tyr maps, following the game's rules (BP_TyrGameMode, BP_VisionBlocker, TankData):
//!   a tank is spotted when there is line of sight to any part of it and the distance is within
//!   VisionRadius * (1 - camo/100); camo is capped at 80. A sight line that passes within 3.25 m of a bush centre
//!   gives the target +40 camo (bush camo capped at 40), unless the spotter is within 15 m of that bush (see-through).
//! Input dir: grid.bin written by tools/maplos.py. Output per camo level k: sees_k.f32 (m² of playable ground where an
//! enemy with that camo would be spotted from here), seen_k.f32 (observer positions that spot a tank with that camo here),
//! zones_k.u8 (per zone, per observer cell: 1 if a tank here spots an enemy sitting on the zone centre).
use rayon::prelude::*;
use std::fs;
use std::io::Read;

struct Grid { w: usize, h: usize, res: f32, ground: Vec<f32>, block: Vec<f32>, play: Vec<u8>, bush_id: Vec<i32>, bushes: Vec<(f32, f32)> }
struct P { radius: usize, eye: f32, tgt: f32, stride: usize, vision_m: f32, max_camo: f32, bush_camo: f32, see_through_m: f32, camos: Vec<f32>, zones: Vec<(usize, usize)> }

fn read(path: &str) -> (Grid, P) {
    let mut b = Vec::new(); fs::File::open(path).expect("grid.bin").read_to_end(&mut b).unwrap();
    let mut o = 0usize;
    let mut u = || { let v = u32::from_le_bytes(b[o..o + 4].try_into().unwrap()) as usize; o += 4; v };
    let (w, h) = (u(), u());
    let res = f32::from_bits(u() as u32);
    let radius = u(); let eye = f32::from_bits(u() as u32); let tgt = f32::from_bits(u() as u32); let stride = u();
    let vision_m = f32::from_bits(u() as u32); let max_camo = f32::from_bits(u() as u32); let bush_camo = f32::from_bits(u() as u32);
    let bush_r_m = f32::from_bits(u() as u32); let see_through_m = f32::from_bits(u() as u32);
    let nc = u(); let camos: Vec<f32> = (0..nc).map(|_| f32::from_bits(u() as u32)).collect();
    let nz = u(); let zones: Vec<(usize, usize)> = (0..nz).map(|_| (u(), u())).collect();
    let nb = u(); let bushes: Vec<(f32, f32)> = (0..nb).map(|_| (f32::from_bits(u() as u32), f32::from_bits(u() as u32))).collect();
    let n = w * h;
    let rf = |o: &mut usize| { let v: Vec<f32> = (0..n).map(|i| f32::from_le_bytes(b[*o + 4 * i..*o + 4 * i + 4].try_into().unwrap())).collect(); *o += 4 * n; v };
    let ground = rf(&mut o); let block = rf(&mut o);
    let play = b[o..o + n].to_vec();
    // bush footprint: cell -> bush index (nearest bush within its vision-blocker radius)
    let mut bush_id = vec![-1i32; n];
    let rc = bush_r_m / res;
    for (k, &(bx, by)) in bushes.iter().enumerate() {
        let (x0, x1) = ((bx - rc).floor().max(0.0) as usize, ((bx + rc).ceil() as usize).min(w - 1));
        let (y0, y1) = ((by - rc).floor().max(0.0) as usize, ((by + rc).ceil() as usize).min(h - 1));
        for y in y0..=y1 { for x in x0..=x1 {
            let (dx, dy) = (x as f32 - bx, y as f32 - by);
            if dx * dx + dy * dy <= rc * rc { bush_id[y * w + x] = k as i32; }
        } }
    }
    (Grid { w, h, res, ground, block, play, bush_id, bushes }, P { radius, eye, tgt, stride, vision_m, max_camo, bush_camo, see_through_m, camos, zones })
}

/// sweep sight lines from (ox, oy); for every playable target cell call mark(x, y, dist_m, bush_bonus)
fn sweep(g: &Grid, p: &P, ox: usize, oy: usize, mut mark: impl FnMut(usize, usize, f32, bool)) {
    let e = g.ground[oy * g.w + ox] + p.eye;
    let r = p.radius as i64;
    let see_through_c2 = (p.see_through_m / g.res).powi(2);
    let mut perim = Vec::with_capacity((8 * r) as usize);
    for i in -r..=r { perim.push((i, -r)); perim.push((i, r)); }
    for i in -r + 1..r { perim.push((-r, i)); perim.push((r, i)); }
    for (px, py) in perim {
        let steps = px.abs().max(py.abs());
        let mut maxs = f32::NEG_INFINITY;
        let mut bush = false;
        for s in 1..=steps {
            let t = s as f32 / steps as f32;
            let (xi, yi) = ((ox as f32 + px as f32 * t).round() as i64, (oy as f32 + py as f32 * t).round() as i64);
            if xi < 0 || yi < 0 || xi >= g.w as i64 || yi >= g.h as i64 { break; }
            let (xi, yi) = (xi as usize, yi as usize);
            let idx = yi * g.w + xi;
            let (dx, dy) = (xi as f32 - ox as f32, yi as f32 - oy as f32);
            let d = (dx * dx + dy * dy).sqrt().max(0.5);
            if d > r as f32 { break; }
            let b = g.bush_id[idx];
            if b >= 0 && !bush {
                let (bx, by) = g.bushes[b as usize];
                let (ddx, ddy) = (bx - ox as f32, by - oy as f32);
                if ddx * ddx + ddy * ddy > see_through_c2 { bush = true; }   // the spotter is outside this bush's see-through range
            }
            // any part of the target column above the highest obstacle so far counts as line of sight
            let top = (g.ground[idx] + p.tgt - e) / d;
            if top >= maxs && g.play[idx] != 0 { mark(xi, yi, d * g.res, bush); }
            let os = (g.block[idx] - e) / d;
            if os > maxs { maxs = os; }
        }
    }
}

fn main() {
    let dir = std::env::args().nth(1).expect("map dir");
    let (g, p) = read(&format!("{dir}/grid.bin"));
    let n = g.w * g.h; let cell_area = g.res * g.res;
    let obs: Vec<(usize, usize)> = (0..g.h).step_by(p.stride).flat_map(|y| (0..g.w).step_by(p.stride).map(move |x| (x, y)))
        .filter(|&(x, y)| g.play[y * g.w + x] != 0).collect();
    eprintln!("{}x{} cells, {} observers, {} bushes, camo levels {:?}", g.w, g.h, obs.len(), g.bushes.len(), p.camos);
    let spot_range = |camo: f32, bush: bool| { let c = (camo + if bush { p.bush_camo } else { 0.0 }).min(p.max_camo); p.vision_m * (1.0 - c / 100.0) };
    for (k, &camo) in p.camos.iter().enumerate() {
        let results: Vec<(usize, f32, Vec<u32>, Vec<u8>)> = obs.par_iter().map(|&(ox, oy)| {
            let mut hit = std::collections::HashSet::new();
            sweep(&g, &p, ox, oy, |x, y, dist, bush| { if dist <= spot_range(camo, bush) { hit.insert((y * g.w + x) as u32); } });
            let zv: Vec<u8> = p.zones.iter().map(|&(zx, zy)| hit.contains(&((zy * g.w + zx) as u32)) as u8).collect();
            let cells: Vec<u32> = hit.into_iter().collect();
            (oy * g.w + ox, cells.len() as f32 * cell_area, cells, zv)
        }).collect();
        let mut sees = vec![f32::NAN; n]; let mut seen = vec![0f32; n]; let mut zmap = vec![0u8; p.zones.len() * n];
        for (o, area, cells, zv) in &results {
            sees[*o] = *area;
            for &c in cells { seen[c as usize] += 1.0; }
            for (z, &v) in zv.iter().enumerate() { zmap[z * n + *o] = v; }
        }
        let wf = |name: String, v: &[f32]| fs::write(format!("{dir}/{name}"), v.iter().flat_map(|x| x.to_le_bytes()).collect::<Vec<u8>>()).unwrap();
        wf(format!("sees_{k}.f32"), &sees); wf(format!("seen_{k}.f32"), &seen);
        fs::write(format!("{dir}/zones_{k}.u8"), &zmap).unwrap();
    }
    eprintln!("done");
}
