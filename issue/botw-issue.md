**Device:** POCO X7 Pro (Xiaomi 2412DPC0AG), Dimensity 8400 (MT6899), Mali-G720 MC7, Arm driver v1.r49p1-03bet0.4fc328bba6e40f10f4bc96d62f5ee40a, Android 16, 12 GB (11 GiB reported)
**Game:** 1.9.0, Recompiled mode

### 1. 0.4.12's write-fault run fixes the mappings crash on a long Mali session

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

### 2. LARECOMP_WT_FAULT_RUN_KB=256 lowers uploads with no measurable cost

With the default 1024 KB, uploads roughly doubled compared with 0.4.11 (146-203 MB per 2 s window, against 69-86 MB). The reopened run's pages count as written, so they are uploaded again (31.5 M pages reopened in 30 min).

With `LARECOMP_WT_FAULT_RUN_KB=256` (Driver variables), on the same kind of scenes:

| Per 2 s window | 1024 KB | 256 KB |
|---|---|---|
| Upload, fast / medium / slow windows | 146 / 203 / 192 MB | 98 / 133 / 117 MB (**−35%**) |
| Median fps | 21.8 | 22.4 |
| Mappings at 5 min | 12,297 | 12,277 |
| Mappings after 56 min | — | 15,244 |

fps did not change: on this phone the GPU is the limit (overlay: GPU 34.1 ms of a 35.9 ms frame). A smaller default for Mali copy mode might still be worth it, as it is less work for the same mappings.

### 3. In-place draw-target reads (0.4.13) removed the worst drops

On 0.4.11, the slowest windows (17.2 fps on average) had about 2,750 framebuffer copies per 2 s, against 200 in the 30 fps windows. On 0.5.0 `fbcopy` is 0 everywhere. The 10th-percentile fps went from 16.5 to 19.7, and the time under 20 fps from 32% to 13%.

Best result so far (56 min, system driver, WT_FAULT_RUN_KB=256, SGSR 1, 720p internal, shadows off, 30 fps cap): mean 26.9 fps, median 27.2, 10th percentile 22.3, 63% of the time at ≥26 fps.

### 4. PanVK faux123 v1.1.8 with "Game memory on the GPU: On" reboots the whole phone

The driver loads fine (`loaded through adrenotools`, `placed maps yes`, `BC 1`). Then:

    22:41:40.109 [vk] guest heap 3120 MB is GPU memory (placed at 340000000, memory type 1, flags 0x7, storage range 4095 MB)
    22:41:40.112 init main (DT_INIT 10000e8e0, 1040 init_array entries)
    ...
    22:41:40.264 [ipc] control 2 on fsp-srv (handle 112)
    <log ends: the phone froze and rebooted>

Starting again with PanVK still selected hung the phone a second time, while still on the start screen; the log was cut off with NUL bytes. The long-press "System driver" shortcut recovered it.

My guess, not proven: placing the whole 3.1 GB heap at once is more than PanVK on Arm's mali_kbase can handle on this GPU. I did not try PanVK with the GPU heap Off.

Logs: I will attach them in a comment (0.4.11 crash, 0.5.0 35 min at 1024 KB, 0.5.0 10 min at 256 KB, 0.5.0 56 min at 256 KB, and the PanVK session cut off by the reboot).
