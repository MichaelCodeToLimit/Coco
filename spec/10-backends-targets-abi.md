# 10 — Back Ends, Targets and ABI

*Edition 2026. **[N]** normative, **[I]** informative.*

---

## 10.1 Target triples **[N]**

Coco uses conventional triples, written punctuation-free in `project.coco` and with
hyphens on the command line:

```coco
targets
  x86 64 windows
  x86 64 linux gnu
  aarch64 macos
  aarch64 linux gnu
  aarch64 android
  aarch64 ios
  wasm32 browser
  wasm32 wasi
```

```bash
compose release --target aarch64-macos
compose target list
compose target add wasm32-browser
```

### 10.1.1 Tier policy **[N]**

| Tier | Meaning | Targets |
| --- | --- | --- |
| **1** | Full test suite runs in CI on real hardware; conformance guaranteed | `x86-64-linux-gnu`, `x86-64-windows`, `aarch64-macos`, `wasm32-browser` |
| **2** | Builds and passes the suite under emulation | `aarch64-linux-gnu`, `aarch64-android`, `aarch64-ios`, `wasm32-wasi`, `x86-64-macos` |
| **3** | Builds; community maintained | `riscv64-linux-gnu`, `x86-64-freebsd`, bare-metal `aarch64-none` |

## 10.2 Back-end selection **[N]**

| Back end | Used for | Why |
| --- | --- | --- |
| **Cranelift** | `compose` (dev) on all CPU targets | sub-second codegen, built for JIT, good enough code for development |
| **LLVM** | `release`, `extreme`, `small` | best-in-class optimisation, LTO, PGO, mature target coverage |
| **SPIR-V** | Vulkan device code | standard, consumed by Vulkan and by `naga` for portability |
| **WGSL** | WebGPU device code | browser targets |
| **CIR interpreter** | bootstrap, const-eval, replay | no native codegen dependency |

Both CPU back ends consume **MIR**, a thin target-shaped layer below CIR-C, so back-end
specific work is not duplicated. Adding a third CPU back end means writing one MIR
lowering.

An implementation MAY ship only LLVM (using it at `-O0` for dev builds) and remain
conformant, but SHOULD ship a fast dev back end because the sub-100 ms edit-to-run target
of [doc 09 §9.2](09-compiler-pipeline.md) is hard to hit otherwise.

## 10.3 MIR **[N]**

MIR differs from CIR-C in that it has:

- explicit stack slots and calling-convention-shaped call sites;
- target integer/pointer widths resolved;
- vector widths resolved (from scalable to concrete, where the target requires);
- trap sites materialised as calls to `runtime.trap` with a reason code;
- region operations lowered to allocator calls or pointer arithmetic;
- refcount operations lowered to inline sequences or calls.

MIR is not canonical and is not hashed.

## 10.4 Runtime **[N]**

The Coco runtime is a static library linked into every program. It is **small by
design** and layered so embedded and WASM targets can omit layers.

| Layer | Size (x86-64, release, approx) | Contents | Omittable |
| --- | --- | --- | --- |
| `core` | ~18 KB | traps, region allocator, refcount, text, list, table | no |
| `sched` | ~26 KB | work-stealing pool, handler scheduler, timers | yes (`single threaded`) |
| `io` | ~34 KB | files, sockets, async completion (io_uring / IOCP / kqueue) | yes |
| `ui` | ~180 KB | view diffing, layout, platform windowing | yes |
| `draw` | ~220 KB | 2D/3D renderer, shader runtime | yes |
| `tensor` | ~140 KB | tensor ops, BLAS-level kernels, device dispatch | yes |

Hello-world binary sizes (targets, not guarantees): **x86-64 Linux ≈ 64 KB stripped**,
**wasm32 browser ≈ 22 KB brotli**, achieved with section GC and the `small` profile.

### 10.4.1 Allocator **[N]**

- **Region allocator**: bump pointer per region, chunked (64 KB chunks by default), with
  a free-chunk cache per worker thread. Region teardown is a chunk-list splice.
- **Unique heap**: a size-classed allocator (mimalloc-class design) with per-thread
  heaps and cross-thread free lists.
- **Shared**: same as unique heap plus a refcount header.
- An application may supply its own: `use my allocator as the heap allocator` — required
  for console and embedded targets.

### 10.4.2 No runtime on the hot path **[I]**

There is no interpreter loop, no JIT warm-up, no GC safepoint polling, and no
per-allocation bookkeeping for classes 1–3 of the storage ladder. A tight numeric loop
in Coco compiles to the same machine code you would get from C, because by the time
MIR is reached the region and aliasing facts are stronger than C's.

## 10.5 GPU and device targets **[N]**

### 10.5.1 What can run on a device

A function is **device-eligible** if its effects are a subset of
`{ reads, writes, allocates(device region), device D }` — no `io`, no `blocks`, no host
allocation, no `trusted` operations.

### 10.5.2 Lowering

```
CIR-C device region ─► device MIR ─► SPIR-V   (Vulkan, native)
                                  └► WGSL     (WebGPU, browser)
```

- Control flow is structurised (SPIR-V requires structured control flow); irreducible
  control flow in a device region is `E-1051` with the offending loop named.
- `list of T` becomes a storage buffer; `arr<T,n>` becomes a workgroup array.
- Bounds checks are preserved; out-of-range on a device sets a device-side trap flag
  which the host checks after `device.exit` and converts to a host trap with the
  originating source span.
- Floating-point contraction (FMA) is **off** by default so device and host results
  match bit for bit; `allow fused multiply add` opts in per region.

### 10.5.3 Transfers **[N]**

Every value crossing a device boundary is an explicit transfer in CIR-C
(`device.enter … transfers …`). The compiler:

- elides transfers for values already resident (tracked per buffer across regions);
- reports every transfer and its size in `compose explain transfers`;
- refuses to implicitly transfer a value larger than `transfer warning size`
  (default 64 MB) without an explicit `move … to the gpu`.

### 10.5.4 Tensors **[I]**

The `tensor` module ([doc 11 §11.8](11-stdlib.md)) is ordinary Coco over device
regions; there is no special tensor compiler. Fusion of elementwise chains, tiling of
matrix multiplies and kernel selection are the loop-nest optimiser
([doc 09 §9.5](09-compiler-pipeline.md)) applied to device MIR, plus a small library of
hand-tuned microkernels selected by shape.

## 10.6 WebAssembly **[N]**

| Aspect | Decision |
| --- | --- |
| Memory model | `wasm32` linear memory; `memory64` behind a flag |
| Threads | `wasm32-browser` uses shared memory + atomics when `crossOriginIsolated`; otherwise the scheduler degrades to a single worker and reports `I-1061` |
| GC proposal | not used — Coco manages its own memory |
| Exceptions | not used — traps become `unreachable` with a side table mapping to reason codes |
| Host interface | `wasm32-browser`: generated JS glue, with the whole `ui`/`draw` layer targeting WebGPU + Canvas. `wasm32-wasi`: WASI preview 2 components |
| Component model | `compose release --target wasm32-wasi --component` emits a WIT-described component |

The `ui` module's browser back end renders to **Canvas/WebGPU**, not to the DOM. This is
deliberate: Coco's view model is its own, and mapping it onto HTML/CSS would
reintroduce the six-language problem Rule 5 exists to remove. A DOM back end is available
as an opt-in package for accessibility-sensitive applications and is required to be used
when `accessibility native` is set.

## 10.7 The C ABI **[N]**

Coco's foreign interface is `coco_abi_v1`, a C ABI.

### 10.7.1 Calling out

```coco
this module is trusted because it wraps libsqlite3

the foreign library sqlite3

to open a database at a path giving a whole number
  foreign sqlite3_open
    path as a c text
    handle as a pointer to a pointer
```

### 10.7.2 Type mapping **[N]**

| Coco | C |
| --- | --- |
| `whole number` | `int64_t` |
| `whole number of 32 bits` | `int32_t` |
| `decimal number` | `double` |
| `yes or no` | `bool` (1 byte) |
| `text` | **not** directly; use `a c text` (NUL-terminated UTF-8) or `a text span` (ptr+len) |
| a record marked `laid out together` | `struct` with C layout and C field order |
| `list of T` | `a span of T` (ptr + len), or `a c array of T` |
| `maybe T` where T is a pointer type | nullable pointer |
| `own<T>` | pointer; ownership transfer documented by `gives ownership` / `takes ownership` |

A record is only ABI-stable if declared `laid out together`; otherwise the compiler is
free to reorder and to pick struct-of-arrays.

### 10.7.3 Calling in **[N]**

```coco
share as a c function coco_add
to add a first and a second giving a whole number
  give first plus second
```

produces `int64_t coco_add(int64_t, int64_t)` and a generated header. Coco
functions exposed this way:

- must not have `blocks` effects unless the caller drives the scheduler via
  `coco_runtime_poll`;
- trap on overflow, which calls the installed trap handler rather than unwinding into C;
- may be called before `coco_runtime_start` only if they are `pure`.

### 10.7.4 Runtime entry points **[N]**

```c
int  coco_runtime_start(int argc, char** argv);
void coco_runtime_stop(void);
int  coco_runtime_poll(void);          /* drive one scheduler turn */
void coco_set_trap_handler(void (*h)(int32_t reason, const char* where));
void coco_set_allocator(const coco_allocator_v1* a);
```

## 10.8 Traps and process behaviour **[N]**

| Reason code | Meaning |
| --- | --- |
| `1` | integer overflow |
| `2` | division by zero |
| `3` | index out of range |
| `4` | unchecked `maybe` reached `nothing` (compiler bug; should be impossible) |
| `5` | assertion failed |
| `6` | unreachable code reached |
| `7` | region invariant violated (compiler bug) |
| `8` | device trap |
| `9` | allocation failure |
| `10` | deadline exceeded on a `blocks` operation with `deadline is fatal` |

Default behaviour: print reason, source span, handler name and a backtrace with CIDs
resolved to names, then abort. Server targets may install a handler that instead fails
the current **handler** and continues — safe because a handler is a region and its state
writes are staged (see §10.9).

## 10.9 Failure isolation for servers **[N]**

`when a request arrives` handlers run in a **staged** region: their writes to shared
module state are buffered and committed at handler completion. A trap inside the handler
discards the staged writes, frees the region, and returns a 500 without affecting other
in-flight handlers. This gives Erlang-style isolation with zero copying for the common
case, because staging reuses the region's copy-on-write chunks.

Staging is enabled by declaring the handler `isolated`:

```coco
when a request arrives isolated
  ...
```

## 10.10 Linking and distribution **[N]**

- Native: static linking by default; `compose release --dynamic` links the runtime
  dynamically.
- Cross-compilation: `compose target add` downloads a pinned, hash-verified sysroot.
  Cross builds are reproducible and do not require a host toolchain of the target OS
  except where a platform SDK is legally required (iOS, macOS signing).
- Output: a single executable, plus `app.coco.hash`, plus optional split debug info
  (`app.cocodbg`).
- `compose bundle` produces platform packages (`.app`, `.msix`, `.apk`, `.wasm` + loader).

---

*Next: [11 — Standard library](11-stdlib.md)*
