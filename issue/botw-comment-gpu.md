Follow-up: where the GPU time goes on the Mali-G720, and an A/B of the long-pass split.

Same phone, 0.5.0, Arm r49p1, Recompiled, `LARECOMP_WT_FAULT_RUN_KB=256`.

### GPU time per pass (`LARECOMP_GPUPROF_AT=9000`, G-buffer at 1600x900): 36.75 ms

| Work | GPU | Passes |
|---|---|---|
| G-buffer / lighting at full res (6-8 colour targets + depth) | 12.4 ms | 9 |
| Other mid-size passes | 9.0 ms | 44 |
| Other full-res passes | 6.1 ms | 15 |
| Tiny passes (< 0.07 ms each: 16x16 / 64x64 faces, mip chains, 1x1 …) | **4.3 ms** | **89** |
| Compute | 2.1 ms | 19 |
| Depth-only (shadows) | 2.0 ms | 5 |

- Each tiny pass costs ~0.04 ms even when it draws one 16x16 quad, which adds up to ~12% of the frame. `begin_pass` puts `vk_full_barrier` before every pass, so consecutive small passes can't overlap. Tracking the real dependencies (or a lighter barrier between passes that don't read each other's targets) looks like the biggest engine-side gain left on Mali.
- In that frame the G-buffer pass (6 colour + depth, 1600x900) came out as 4 passes with a submission between each: 1.97 / 1.67 / 2.16 / 2.60 ms. That is `split_long_pass` (`LARECOMP_VK_SPLIT_US`, 3000 by default on non-Qualcomm drivers).
- `LARECOMP_VK_PROF` pass ends: almost all at exec.c:2492 (render targets change, ~7,800 per 2 s); ~250 per 2 s at submissions.

### A/B of the long-pass split: `LARECOMP_AB=300:split`, `LARECOMP_LOG_PACE=1`

~24,800 in-world frames, alternating every 300 frames in the same session:

| | split on (default) | split off |
|---|---|---|
| GPU per frame (mean) | 35.66 ms | 35.25 ms |
| Frame period (mean) | 38.74 ms (25.8 fps) | 38.04 ms (26.3 fps) |
| Frames over 34 ms | 68% | 65% |

Over 81 adjacent block pairs, split off is **0.78 ± 0.25 ms per frame faster** (period). The GPU difference (0.50 ± 0.49 ms) is within noise. It is a small but consistent gain, so `LARECOMP_VK_SPLIT_US=0` could be a reasonable default on Mali, where the GPU, not the render thread, is the limit. The stores and reloads cost less than I expected; maybe AFBC compresses them.

For reference, lowering the scene from 1600x900 to 1500x675 (SGSR 1 to 720p) in the same session took the GPU from ~36.5 to ~33.3 ms and the frame rate from ~25.5 to ~27.1 fps (different areas, so approximate). The render thread is then at ~26.5 ms, close to the GPU.

### Two smaller notes

- `nvnCommandBufferDiscardDepthStencil` is a no-op (cmdbuf.c), and every pass stores depth (`storeOp = STORE`). Honouring the discard (a look-ahead like the clear-load one, only when no split or in-place read can reopen the pass) would save a depth store per pass on tilers. I haven't measured it.
- About the PanVK reboot in my first post: the comment in device.c about #118 (Mali-G610 r56p0: "the 3 GB heap imported at once … froze Android") matches what happened here with PanVK placing 3,120 MB at once. So the hang is probably the Mali kernel driver with one huge GPU allocation, not PanVK as such. Placing the heap in parts (as Swap2-Native's `low_ram_place_part_mb` does) might make the placed path usable on Mali.

Logs: the GPUPROF/VK_PROF session and the A/B session (3.7 MB).
