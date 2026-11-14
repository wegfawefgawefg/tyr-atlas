//! Viewshed sweep for Tyr maps.
//! Input dir: grid.bin (header + f32 dtm, f32 dsm_vision, u8 playable, u8 bush) written by tools/maplos.py.
//! Output: sees.f32 (per cell, m² of playable ground visible from a tank here), seen.f32 (per cell, number of observer
//! positions that see a tank here), zones.u8 (per zone, per cell: 1 if a tank here sees the zone centre).
use rayon::prelude::*;
use std::fs;
use std::io::Read;

struct Grid { w: usize, h: usize, res: f32, dtm: Vec<f32>, dsm: Vec<f32>, dsm0: Vec<f32>, play: Vec<u8>, bush: Vec<u8> }

fn read_grid(path: &str) -> (Grid, Vec<(usize, usize)>, usize, f32, f32, usize, f32) {
    let mut f = fs::File::open(path).expect("grid.bin");
    let mut b = Vec::new(); f.read_to_end(&mut b).unwrap();
    let u = |o: usize| u32::from_le_bytes(b[o..o + 4].try_into().unwrap()) as usize;
    let fl = |o: usize| f32::from_le_bytes(b[o..o + 4].try_into().unwrap());
    let (w, h, res) = (u(0), u(4), fl(8));
    let radius = u(12); let eye = fl(16); let tgt = fl(20); let stride = u(24); let bush_conceal = fl(28);
    let nz = u(32);
    let mut o = 36;
    let mut zones = Vec::new();
    for _ in 0..nz { zones.push((u(o), u(o + 4))); o += 8; }
    let n = w * h;
    let rd = |o: &mut usize| { let v: Vec<f32> = (0..n).map(|i| fl(*o + 4 * i)).collect(); *o += 4 * n; v };
    let dtm = rd(&mut o); let dsm = rd(&mut o); let dsm0 = rd(&mut o);
    let play = b[o..o + n].to_vec(); o += n;
    let bush = b[o..o + n].to_vec();
    (Grid { w, h, res, dtm, dsm, dsm0, play, bush }, zones, radius, eye, tgt, stride, bush_conceal)
}

/// visibility from observer (ox, oy): calls mark(x, y) for every playable target cell a tank-height target is visible in
fn sweep(g: &Grid, ox: usize, oy: usize, radius: usize, eye: f32, tgt: f32, bush_conceal_cells: f32, mut mark: impl FnMut(usize, usize, f32)) {
    let e = g.dtm[oy * g.w + ox] + eye;
    let r = radius as i64;
    let mut perim = Vec::with_capacity((8 * r) as usize);
    for i in -r..=r { perim.push((i, -r)); perim.push((i, r)); }
    for i in -r + 1..r { perim.push((-r, i)); perim.push((r, i)); }
    for (px, py) in perim {
        let steps = px.abs().max(py.abs()) as f32;
        let mut maxs = f32::NEG_INFINITY;
        for s in 1..=(steps as i64) {
            let t = s as f32 / steps;
            let x = ox as f32 + px as f32 * t; let y = oy as f32 + py as f32 * t;
            let (xi, yi) = (x.round() as i64, y.round() as i64);
            if xi < 0 || yi < 0 || xi >= g.w as i64 || yi >= g.h as i64 { break; }
            let (xi, yi) = (xi as usize, yi as usize);
            let idx = yi * g.w + xi;
            let dx = (xi as f32 - ox as f32); let dy = (yi as f32 - oy as f32);
            let d = (dx * dx + dy * dy).sqrt().max(0.5);
            if d * d > (r * r) as f32 { break; }
            // lowest point of the target column that clears every obstacle so far
            let hmin = if maxs == f32::NEG_INFINITY { 0.0 } else { (maxs * d + e - g.dtm[idx]).max(0.0) };
            let expo = ((tgt - hmin) / tgt).clamp(0.0, 1.0);
            if expo > 0.0 && g.play[idx] != 0 && (g.bush[idx] == 0 || d <= bush_conceal_cells) { mark(xi, yi, expo); }
            let top = if d * g.res <= 6.0 { g.dsm0[idx] } else { g.dsm[idx] };   // your own bush doesn't block your view out
            let os = (top - e) / d;
            if os > maxs { maxs = os; }
        }
    }
}

fn main() {
    let dir = std::env::args().nth(1).expect("map dir");
    let (g, zones, radius, eye, tgt, stride, bush_conceal) = read_grid(&format!("{dir}/grid.bin"));
    let cell_area = g.res * g.res;
    let conceal_cells = bush_conceal / g.res;
    let obs: Vec<(usize, usize)> = (0..g.h).step_by(stride).flat_map(|y| (0..g.w).step_by(stride).map(move |x| (x, y)))
        .filter(|&(x, y)| g.play[y * g.w + x] != 0).collect();
    eprintln!("{}x{} cells, {} observers, radius {} cells", g.w, g.h, obs.len(), radius);
    // per observer: visible set -> sees count; seen accumulated per target
    let results: Vec<(usize, f32, Vec<(u32, f32)>, Vec<u8>)> = obs.par_iter().map(|&(ox, oy)| {
        let mut vis = vec![0u8; 0];
        let mut best: std::collections::HashMap<u32, f32> = std::collections::HashMap::new();
        sweep(&g, ox, oy, radius, eye, tgt, conceal_cells, |x, y, e| { let i = (y * g.w + x) as u32; let v = best.entry(i).or_insert(0.0); if e > *v { *v = e; } });
        let cells: Vec<(u32, f32)> = best.into_iter().collect();
        let seen_local: std::collections::HashMap<u32, f32> = cells.iter().cloned().collect();
        // zone coverage: can this observer see each zone centre?
        let zv: Vec<u8> = zones.iter().map(|&(zx, zy)| {
            let dx = zx as f32 - ox as f32; let dy = zy as f32 - oy as f32;
            if (dx * dx + dy * dy).sqrt() > radius as f32 { return 0; }
            let i = (zy * g.w + zx) as u32; if seen_local.get(&i).copied().unwrap_or(0.0) > 0.25 { 1 } else { 0 }
        }).collect();
        vis.clear();
        let area: f32 = cells.iter().map(|c| c.1).sum::<f32>() * cell_area;
        (oy * g.w + ox, area, cells, zv)
    }).collect();
    let n = g.w * g.h;
    let mut sees = vec![f32::NAN; n]; let mut seen = vec![0f32; n];
    let mut zmap = vec![0u8; zones.len() * n];
    for (o, area, cells, zv) in &results {
        sees[*o] = *area;
        for &(c, e) in cells { seen[c as usize] += e; }
        for (k, &v) in zv.iter().enumerate() { zmap[k * n + *o] = v; }
    }
    let wf = |name: &str, v: &[f32]| fs::write(format!("{dir}/{name}"), v.iter().flat_map(|x| x.to_le_bytes()).collect::<Vec<u8>>()).unwrap();
    wf("sees.f32", &sees); wf("seen.f32", &seen);
    fs::write(format!("{dir}/zones.u8"), &zmap).unwrap();
    eprintln!("done");
}
