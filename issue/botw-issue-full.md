**Device:** POCO X7 Pro (Xiaomi 2412DPC0AG), Dimensity 8400 (MT6899), Mali-G720 MC7, Arm driver v1.r49p1-03bet0.4fc328bba6e40f10f4bc96d62f5ee40a, Android 16, 12 GB (11 GiB reported)
**Game:** 1.9.0, Recompiled mode

Results from several long sessions on a Mali-G720, the phone you are raising money for. In short: 0.5.0 fixes the memory-mappings crash, two settings help, and there are a few engine-side leads.

## 1. 0.4.12's write-fault run fixes the mappings crash on a long session

You wrote in aa34207 that the gain on a long Mali session was not shown yet. Here it is.

**0.4.11:** closed after ~41 min with `signal 6` in `malloc` called from `libGLES_mali.so` (render thread, `vk_execute_now`). The 5-minute mappings line grew steadily until Android's limit:

| Time | Mappings | (no name) | scudo:secondary |
|---|---|---|---|
| 1 min | 4,953 | 1,272 | 219 |
| 16 min | 33,533 | 12,793 | 9,312 |
| 31 min | 52,896 | 23,524 | 16,803 |
| 41 min | **64,254** → crash | 30,447 | 21,092 |

malloc in use at the end: 2,196 MB.

**0.5.0 (system driver):** mappings stop at 14-15k.
- 35-min session: 12,297 at 6 min, 15,323 at 31 min, malloc 532 MB, no crash.
- 56-min session (with the setting below): 4,877 → 12,440 → 14,397 → … → 15,244 at the end, malloc 578 MB, no crash.

## 2. `LARECOMP_WT_FAULT_RUN_KB=256` lowers uploads at no measurable cost

With the default 1024 KB, uploads roughly doubled compared with 0.4.11 (146-203 MB per 2 s window, against 69-86 MB). The reopened run's pages count as written, so they are uploaded again (31.5 M pages reopened in 30 min). With 256 KB, on the same kind of scenes:

| Per 2 s window | 1024 KB | 256 KB |
|---|---|---|
| Upload, fast / medium / slow windows | 146 / 203 / 192 MB | 98 / 133 / 117 MB (**−35%**) |
| Median fps | 21.8 | 22.4 |
| Mappings at 5 min | 12,297 | 12,277 |
| Mappings after 56 min | — | 15,244 |

fps did not change, because the GPU is the limit on this phone (see 4). It still seems a better default for Mali copy mode: less work for the same mappings.

## 3. In-place draw-target reads (0.4.13) removed the worst drops

On 0.4.11, the slowest windows (17.2 fps on average) had about 2,750 framebuffer copies per 2 s, against 200 in the 30 fps windows. On 0.5.0 `fbcopy` is 0 everywhere. The 10th-percentile fps went from 16.5 to 19.7, and the time under 20 fps from 32% to 13%.

## 4. Where the GPU time goes (`LARECOMP_GPUPROF_AT=9000`, G-buffer at 1600x900): 36.75 ms

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

## 5. A/B of the long-pass split (`LARECOMP_AB=300:split`, `LARECOMP_LOG_PACE=1`)

~24,800 in-world frames, alternating every 300 frames in the same session:

| | split on (default) | split off |
|---|---|---|
| GPU per frame (mean) | 35.66 ms | 35.25 ms |
| Frame period (mean) | 38.74 ms (25.8 fps) | 38.04 ms (26.3 fps) |
| Frames over 34 ms | 68% | 65% |

Over 81 adjacent block pairs, split off is **0.78 ± 0.25 ms per frame faster** (period). The GPU difference (0.50 ± 0.49 ms) is within noise. It is a small but consistent gain, so `LARECOMP_VK_SPLIT_US=0` could be a reasonable default on Mali, where the GPU, not the render thread, is the limit. The stores and reloads cost less than I expected; maybe AFBC compresses them.

For reference, lowering the scene from 1600x900 to 1500x675 (SGSR 1 to 720p) in the same session took the GPU from ~36.5 to ~33.3 ms and the frame rate from ~25.5 to ~27.1 fps (different areas, so approximate). The render thread is then at ~26.5 ms, close to the GPU. Shadows on cost only ~1-2 fps here.

Best result so far (56 min, WT_FAULT_RUN_KB=256, SGSR 1, 720p internal, shadows off, 30 fps cap): mean 26.9 fps, median 27.2, 10th percentile 22.3, 63% of the time at ≥26 fps.

## 6. PanVK faux123 v1.1.8 with "Game memory on the GPU: On" reboots the whole phone

The driver loads fine (`loaded through adrenotools`, `placed maps yes`, `BC 1`). Then:

    22:41:40.109 [vk] guest heap 3120 MB is GPU memory (placed at 340000000, memory type 1, flags 0x7, storage range 4095 MB)
    22:41:40.112 init main (DT_INIT 10000e8e0, 1040 init_array entries)
    ...
    22:41:40.264 [ipc] control 2 on fsp-srv (handle 112)
    <log ends: the phone froze and rebooted>

Starting again with PanVK still selected hung the phone a second time, while still on the start screen; the log was cut off with NUL bytes. The long-press "System driver" shortcut recovered it.

The comment in device.c about #118 (Mali-G610 r56p0: "the 3 GB heap imported at once … froze Android") matches this. So the hang is probably the Mali kernel driver with one huge GPU allocation, not PanVK as such. Placing the heap in parts (Banana Native and Swap2-Native have a `low_ram_place_part_mb` policy along those lines) might make the placed path usable on Mali. I did not try PanVK with the GPU heap Off.

## 7. A smaller note

`nvnCommandBufferDiscardDepthStencil` is a no-op (cmdbuf.c), and every pass stores depth (`storeOp = STORE`). Honouring the discard (a look-ahead like the clear-load one, only when no split or in-place read can reopen the pass) would save a depth store per pass on tilers. I haven't measured it.

Logs: I will attach them in a comment (0.4.11 crash; 0.5.0 at 1024 KB; 256 KB; 56 min; the PanVK session cut off by the reboot; the GPUPROF/VK_PROF session; the A/B session).
